import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class TextProcessor:
    """Process and understand natural language text"""
    
    def __init__(self):
        self.intent_patterns = {
            "check_stock": [
                r"check\s+stock",
                r"stock\s+level",
                r"how\s+much.*stock",
                r"inventory\s+status"
            ],
            "low_stock": [
                r"low\s+stock",
                r"running\s+low",
                r"need\s+to\s+reorder",
                r"stock\s+alert"
            ],
            "reorder": [
                r"reorder",
                r"purchase\s+more",
                r"buy\s+more",
                r"order\s+items"
            ],
            "add_employee": [
                r"add\s+employee",
                r"new\s+staff",
                r"hire\s+someone",
                r"register\s+employee"
            ],
            "calculate_salary": [
                r"calculate\s+salary",
                r"generate\s+payroll",
                r"salary\s+calculation",
                r"pay\s+calculation"
            ]
        }
        
        self.entity_patterns = {
            "item": r"(?:item|product|stock)\s+([a-zA-Z0-9\s]+)",
            "employee": r"(?:employee|staff|worker)\s+([a-zA-Z\s]+)",
            "quantity": r"(\d+)\s*(?:pieces|units|kg|liters?|pcs)",
            "date": r"(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
            "money": r"\$?(\d+(?:,\d{3})*(?:\.\d{2})?)"
        }
    
    async def process(self, text: str) -> Dict[str, Any]:
        """Process text and extract intent and entities"""
        try:
            text_lower = text.lower()
            
            # Extract intent
            intent = self._extract_intent(text_lower)
            
            # Extract entities
            entities = self._extract_entities(text)
            
            return {
                "intent": intent,
                "entities": entities,
                "processed_text": text_lower,
                "confidence": 0.8  # Simple confidence score
            }
            
        except Exception as e:
            logger.error(f"Error processing text: {str(e)}")
            return {
                "intent": "unknown",
                "entities": [],
                "processed_text": text.lower(),
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _extract_intent(self, text: str) -> str:
        """Extract intent from text"""
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return intent
        return "general_query"
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text"""
        entities = []
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append({
                    "type": entity_type,
                    "value": match.group(1).strip(),
                    "start": match.start(),
                    "end": match.end()
                })
        
        return entities