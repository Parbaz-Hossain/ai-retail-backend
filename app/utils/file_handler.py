import os
import uuid
import aiofiles
from pathlib import Path
from typing import Optional, Dict, Set
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import logging
import mimetypes

logger = logging.getLogger(__name__)

class FileUploadService:
    def __init__(self):
        self.upload_dir = Path("uploads")
        
        # Image types and settings
        self.allowed_image_types = {
            "image/jpeg", "image/jpg", "image/png", "image/webp", 
            "image/gif", "image/bmp", "image/tiff"
        }
        self.max_image_size = 5 * 1024 * 1024  # 5MB for images
        
        # Document types and settings
        self.allowed_document_types = {
            # PDF
            "application/pdf",
            # Microsoft Office
            "application/msword",  # .doc
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
            "application/vnd.ms-excel",  # .xls
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
            "application/vnd.ms-powerpoint",  # .ppt
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
            # Text files
            "text/plain",  # .txt
            "text/csv",  # .csv
            "application/rtf",  # .rtf
            # Archives
            "application/zip",
            "application/x-rar-compressed",
            "application/x-7z-compressed",
            # Other formats
            "application/json",
            "application/xml",
            "text/xml",
        }
        self.max_document_size = 10 * 1024 * 1024  # 10MB for documents
        
        # File extension mapping for better validation
        self.image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}
        self.document_extensions = {
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".txt", ".csv", ".rtf", ".zip", ".rar", ".7z", ".json", ".xml"
        }
        
    async def create_upload_dirs(self, entity_type: str = None):
        """Create upload directories if they don't exist"""
        # Create base directories
        base_dirs = ["documents", "images"]
        for dir_name in base_dirs:
            dir_path = self.upload_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create entity-specific subdirectories if entity_type is provided
        if entity_type:
            entity_dirs = [
                self.upload_dir / "documents" / entity_type,
                self.upload_dir / "images" / entity_type
            ]
            for dir_path in entity_dirs:
                dir_path.mkdir(parents=True, exist_ok=True)
    
    def get_file_type(self, file: UploadFile) -> str:
        """Determine if file is image or document"""
        content_type = file.content_type or ""
        filename = file.filename or ""
        file_extension = Path(filename).suffix.lower()
        
        # Check by content type first
        if content_type in self.allowed_image_types:
            return "image"
        elif content_type in self.allowed_document_types:
            return "document"
        
        # Fallback to extension check
        if file_extension in self.image_extensions:
            return "image"
        elif file_extension in self.document_extensions:
            return "document"
        
        return "unknown"
    
    def validate_file(self, file: UploadFile) -> Dict[str, any]:
        """Validate file type and size, return file info"""
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided"
            )
        
        file_type = self.get_file_type(file)
        
        if file_type == "unknown":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Allowed: Images (JPEG, PNG, WebP, GIF, BMP, TIFF) and Documents (PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT, CSV, ZIP, etc.)"
            )
        
        # Get file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        # Validate size based on file type
        if file_type == "image" and file_size > self.max_image_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image size too large. Max: {self.max_image_size // (1024*1024)}MB"
            )
        elif file_type == "document" and file_size > self.max_document_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document size too large. Max: {self.max_document_size // (1024*1024)}MB"
            )
        
        return {
            "file_type": file_type,
            "file_size": file_size,
            "is_valid": True
        }
    
    async def save_file(self, file: UploadFile, entity_type: str, entity_id: int) -> str:
        """Save file (image or document) and return file info"""
        # Create upload directories including entity-specific ones
        await self.create_upload_dirs(entity_type)
        file_info = self.validate_file(file)
        
        # Generate unique filename
        original_filename = file.filename
        file_extension = Path(original_filename).suffix.lower()
        unique_filename = f"{entity_id}_{uuid.uuid4().hex[:8]}{file_extension}"
        
        # Determine subdirectory based on file type and entity type
        file_type = file_info["file_type"]
        if file_type == "image":
            subdirectory = f"images/{entity_type}"
        else:
            subdirectory = f"documents/{entity_type}"
        
        # Create the full file path
        file_path = self.upload_dir / subdirectory / unique_filename
        
        # Ensure the directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Read and save file
            content = await file.read()
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            # Optimize only if it's an image
            if file_type == "image":
                await self._optimize_image(file_path)
            
            return f"/uploads/{subdirectory}/{unique_filename}"
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            if file_path.exists():
                file_path.unlink()  # Clean up on error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save file"
            )
    
    async def _optimize_image(self, file_path: Path):
        """Optimize image size and quality"""
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary (but preserve transparency for PNG)
                if img.mode == 'RGBA' and file_path.suffix.lower() != '.png':
                    img = img.convert('RGB')
                elif img.mode in ('LA', 'P'):
                    img.convert('RGB')
                
                # Resize if too large
                max_dimension = 1024
                if max(img.size) > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                
                # Save with optimization based on format
                if file_path.suffix.lower() in ['.jpg', '.jpeg']:
                    img.save(file_path, optimize=True, quality=85)
                elif file_path.suffix.lower() == '.png':
                    img.save(file_path, optimize=True)
                elif file_path.suffix.lower() == '.webp':
                    img.save(file_path, optimize=True, quality=85)
                else:
                    img.save(file_path, optimize=True)
                
        except Exception as e:
            logger.error(f"Error optimizing image: {e}")
            # Don't raise error, just log it
 
    def delete_file(self, file_path: str) -> bool:
        """Delete a file from the upload directory"""
        try:
            # Remove leading slash and ensure it's in uploads directory
            clean_path = file_path.lstrip('/')
            full_path = Path(clean_path)
            
            # Security check: ensure file is within uploads directory
            if not str(full_path).startswith('uploads/'):
                logger.warning(f"Attempted to delete file outside uploads directory: {file_path}")
                return False
            
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
                logger.info(f"Successfully deleted file: {file_path}")
                return True
            else:
                logger.warning(f"File not found: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, any]]:
        """Get information about an uploaded file"""
        try:
            clean_path = file_path.lstrip('/')
            full_path = Path(clean_path)
            
            if not str(full_path).startswith('uploads/'):
                return None
                
            if full_path.exists() and full_path.is_file():
                stat = full_path.stat()
                return {
                    "filename": full_path.name,
                    "size": stat.st_size,
                    "created": stat.st_ctime,
                    "modified": stat.st_mtime,
                    "extension": full_path.suffix,
                    "mime_type": mimetypes.guess_type(str(full_path))[0]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return None