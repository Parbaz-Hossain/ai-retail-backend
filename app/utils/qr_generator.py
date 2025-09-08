import qrcode
import json
import uuid
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system.qr_code import QRCode
import logging

logger = logging.getLogger(__name__)

class QRCodeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.qr_dir = Path("uploads/qr_codes")
        self.qr_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_qr_image(self, data: str, filename: str) -> str:
        """Generate QR code image and save to file"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save image
            file_path = self.qr_dir / f"{filename}.png"
            img.save(file_path)
            
            return f"/uploads/qr_codes/{filename}.png"
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate QR code"
            )
    
    async def create_item_qr_code(self, item_id: int, item_data: Dict[str, Any], created_by: int) -> QRCode:
        """Create QR code for item"""
        try:
            # Generate unique QR code string
            qr_code_string = f"ITEM-{item_id}-{uuid.uuid4().hex[:8].upper()}"
            
            # Prepare data payload
            data_payload = {
                "type": "ITEM",
                "item_id": item_id,
                "item_code": item_data.get("item_code"),
                "item_name": item_data.get("name"),
                "category": item_data.get("category"),
                "generated_at": datetime.utcnow().isoformat(),
                "qr_code": qr_code_string
            }
            
            # Generate QR code image
            filename = f"item_{item_id}_{uuid.uuid4().hex[:8]}"
            qr_image_path = self.generate_qr_image(
                json.dumps(data_payload), 
                filename
            )
            
            # Save to database
            qr_code_record = QRCode(
                qr_code=qr_code_string,
                qr_code_image=qr_image_path,
                entity_type="ITEM",
                entity_id=item_id,
                data_payload=data_payload,
                created_by=created_by
            )
            
            self.session.add(qr_code_record)
            await self.session.commit()
            await self.session.refresh(qr_code_record)
            
            return qr_code_record
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating item QR code: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create QR code"
            )