# import logging
# from typing import Dict, Any, List
# from app.ai.base_agent import BaseAgent
# from app.services.inventory.item_service import ItemService
# from app.services.inventory.stock_service import StockService
# from app.services.inventory.reorder_service import ReorderService

# logger = logging.getLogger(__name__)

# class InventoryAgent(BaseAgent):
#     """AI Agent for handling inventory-related tasks"""
    
#     def __init__(self):
#         super().__init__("inventory")
#         self.item_service = ItemService()
#         self.stock_service = StockService()
#         self.reorder_service = ReorderService()
    
#     async def initialize(self):
#         """Initialize the inventory agent"""
#         self.commands = {
#             "check_stock": self._check_stock_levels,
#             "low_stock": self._get_low_stock_items,
#             "reorder": self._process_reorder,
#             "stock_movement": self._record_stock_movement,
#             "inventory_count": self._perform_inventory_count,
#             "add_item": self._add_new_item,
#             "update_item": self._update_item_details,
#             "transfer_stock": self._transfer_stock,
#         }
#         logger.info("✅ Inventory Agent initialized with commands")
    
#     async def process_command(self, command: str, context: Dict[str, Any]) -> Dict[str, Any]:
#         """Process inventory-related commands"""
#         try:
#             # Extract intent and entities
#             intent = context.get("intent")
#             entities = context.get("entities", [])
            
#             # Determine action based on command content
#             if "stock level" in command.lower() or "check stock" in command.lower():
#                 return await self._check_stock_levels(entities, context)
#             elif "low stock" in command.lower() or "running low" in command.lower():
#                 return await self._get_low_stock_items(context)
#             elif "reorder" in command.lower() or "purchase" in command.lower():
#                 return await self._process_reorder(entities, context)
#             elif "add item" in command.lower() or "new product" in command.lower():
#                 return await self._add_new_item(entities, context)
#             elif "transfer" in command.lower():
#                 return await self._transfer_stock(entities, context)
#             else:
#                 return await self._provide_inventory_summary(context)
                
#         except Exception as e:
#             logger.error(f"Error processing inventory command: {str(e)}")
#             return {
#                 "response": f"I encountered an error processing your inventory request: {str(e)}",
#                 "actions": [],
#                 "status": "error"
#             }
    
#     async def _check_stock_levels(self, entities: List[Dict], context: Dict[str, Any]) -> Dict[str, Any]:
#         """Check stock levels for specific items"""
#         try:
#             # Extract item names from entities
#             item_names = [entity["value"] for entity in entities if entity["type"] == "item"]
            
#             if not item_names:
#                 return {
#                     "response": "Please specify which items you'd like to check stock levels for.",
#                     "actions": []
#                 }
            
#             stock_info = []
#             for item_name in item_names:
#                 stock_data = await self.stock_service.get_stock_by_item_name(item_name)
#                 if stock_data:
#                     stock_info.append(f"{item_name}: {stock_data.current_stock} {stock_data.unit}")
#                 else:
#                     stock_info.append(f"{item_name}: Item not found")
            
#             response = "Current stock levels:\n" + "\n".join(stock_info)
            
#             return {
#                 "response": response,
#                 "actions": [{"type": "stock_check", "items": item_names}],
#                 "status": "success"
#             }
            
#         except Exception as e:
#             return {
#                 "response": f"Error checking stock levels: {str(e)}",
#                 "actions": [],
#                 "status": "error"
#             }
    
#     async def _get_low_stock_items(self, context: Dict[str, Any]) -> Dict[str, Any]:
#         """Get list of low stock items"""
#         try:
#             low_stock_items = await self.stock_service.get_low_stock_items()
            
#             if not low_stock_items:
#                 return {
#                     "response": "Great news! All items are adequately stocked.",
#                     "actions": [],
#                     "status": "success"
#                 }
            
#             response_lines = ["⚠️ Low Stock Alert:"]
#             actions = []
            
#             for item in low_stock_items:
#                 response_lines.append(
#                     f"• {item.name}: {item.current_stock} {item.unit} "
#                     f"(Min: {item.min_stock})"
#                 )
#                 actions.append({
#                     "type": "low_stock_alert",
#                     "item_id": item.id,
#                     "item_name": item.name,
#                     "current_stock": item.current_stock,
#                     "min_stock": item.min_stock
#                 })
            
#             response_lines.append("\nWould you like me to create reorder requests for these items?")
            
#             return {
#                 "response": "\n".join(response_lines),
#                 "actions": actions,
#                 "status": "success"
#             }
            
#         except Exception as e:
#             return {
#                 "response": f"Error retrieving low stock items: {str(e)}",
#                 "actions": [],
#                 "status": "error"
#             }
    
#     async def _process_reorder(self, entities: List[Dict], context: Dict[str, Any]) -> Dict[str, Any]:
#         """Process reorder requests"""
#         try:
#             item_names = [entity["value"] for entity in entities if entity["type"] == "item"]
            
#             if not item_names:
#                 # Auto-reorder low stock items
#                 low_stock_items = await self.stock_service.get_low_stock_items()
#                 reorder_results = []
                
#                 for item in low_stock_items:
#                     result = await self.reorder_service.create_reorder_request(
#                         item_id=item.id,
#                         requested_quantity=item.reorder_quantity or (item.max_stock - item.current_stock),
#                         urgency="HIGH" if item.current_stock == 0 else "MEDIUM"
#                     )
#                     reorder_results.append(result)
                
#                 return {
#                     "response": f"Created {len(reorder_results)} reorder requests for low stock items.",
#                     "actions": [{"type": "bulk_reorder", "count": len(reorder_results)}],
#                     "status": "success"
#                 }
#             else:
#                 # Reorder specific items
#                 reorder_results = []
#                 for item_name in item_names:
#                     item = await self.item_service.get_item_by_name(item_name)
#                     if item:
#                         result = await self.reorder_service.create_reorder_request(
#                             item_id=item.id,
#                             requested_quantity=item.reorder_quantity or 10,
#                             urgency="MEDIUM"
#                         )
#                         reorder_results.append((item_name, "success"))
#                     else:
#                         reorder_results.append((item_name, "not_found"))
                
#                 success_count = len([r for r in reorder_results if r[1] == "success"])
                
#                 return {
#                     "response": f"Created reorder requests for {success_count} items.",
#                     "actions": [{"type": "specific_reorder", "items": item_names}],
#                     "status": "success"
#                 }
                
#         except Exception as e:
#             return {
#                 "response": f"Error processing reorder: {str(e)}",
#                 "actions": [],
#                 "status": "error"
#             }
    
#     async def _provide_inventory_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
#         """Provide general inventory summary"""
#         try:
#             summary = await self.stock_service.get_inventory_summary()
            
#             response = f"""📊 Inventory Summary:
#             • Total Items: {summary.get('total_items', 0)}
#             • Low Stock Items: {summary.get('low_stock_count', 0)}
#             • Out of Stock: {summary.get('out_of_stock_count', 0)}
#             • Pending Reorders: {summary.get('pending_reorders', 0)}
#             • Total Value: ${summary.get('total_value', 0):,.2f}

#             How can I help you with inventory management today?"""

#             return {
#                 "response": response,
#                 "actions": [{"type": "inventory_summary", "data": summary}],
#                 "status": "success"
#             }
            
#         except Exception as e:
#             return {
#                 "response": f"Error generating inventory summary: {str(e)}",
#                 "actions": [],
#                 "status": "error"
#             }