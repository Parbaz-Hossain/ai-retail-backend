import os
import uuid
import aiofiles
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class FileUploadService:
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.allowed_image_types = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
        self.max_image_size = 2 * 1024 * 1024  # 2MB
        
    async def create_upload_dirs(self):
        """Create upload directories if they don't exist"""
        dirs = ["users", "employees", "items", "documents"]
        for dir_name in dirs:
            dir_path = self.upload_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def validate_file(self, file: UploadFile) -> bool:
        """Validate image file type and size"""
        if file.content_type not in self.allowed_image_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Allowed: JPEG, PNG, WebP"
            )
            
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > self.max_image_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size too large. Max: {self.max_image_size // (1024*1024)}MB"
            )
        return True
    
    async def save_image(self, file: UploadFile, entity_type: str, entity_id: int) -> str:
        """Save and optimize image file"""
        await self.create_upload_dirs()
        self.validate_file(file)
        
        # Generate unique filename
        file_extension = file.filename.split(".")[-1].lower()
        unique_filename = f"{entity_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = self.upload_dir / entity_type / unique_filename
        
        try:
            # Read and save file
            content = await file.read()
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            # Optimize image
            await self._optimize_image(file_path)
            
            return f"/uploads/{entity_type}/{unique_filename}"
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            if file_path.exists():
                file_path.unlink()  # Clean up on error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save image"
            )
    
    async def _optimize_image(self, file_path: Path):
        """Optimize image size and quality"""
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large
                max_dimension = 1024
                if max(img.size) > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                
                # Save with optimization
                img.save(file_path, optimize=True, quality=85)
                
        except Exception as e:
            logger.error(f"Error optimizing image: {e}")
            # Don't raise error, just log it