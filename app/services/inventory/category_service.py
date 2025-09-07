from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, func, or_

from app.models.inventory.item import Item
from app.models.inventory.category import Category
from app.schemas.inventory.category import CategoryCreate, CategoryUpdate
from app.core.exceptions import NotFoundError, ValidationError

class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_category(self, category_data: CategoryCreate, current_user_id: int) -> Category:
        # Check if parent exists if provided
        if category_data.parent_id:
            parent = await self.get_category_by_id(category_data.parent_id)
            if not parent:
                raise ValidationError("Parent category not found")

        # Check for duplicate name
        existing = await self.db.execute(
            select(Category).where(Category.name == category_data.name)
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Category name already exists")

        category = Category(
            **category_data.model_dump()
        )
        
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        result = await self.db.execute(
            select(Category)
            .options(
                selectinload(Category.children),
                selectinload(Category.parent),
            )
            .where(Category.id == category.id)
        )
        category = result.scalar_one()
        return category

    async def get_category_by_id(self, category_id: int) -> Optional[Category]:
        result = await self.db.execute(
            select(Category)
            .options(selectinload(Category.parent), selectinload(Category.children))
            .where(and_(Category.id == category_id, Category.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_categories(self, 
                             page_index: int = 1, 
                             page_size: int = 100, 
                             search: Optional[str] = None) -> Dict[str, Any]:
        """Get categories with pagination"""
        try:
            query = select(Category).options(
                selectinload(Category.parent),
                selectinload(Category.children)
            ).where(Category.is_active == True)
            
            if search:
                query = query.where(
                    or_(
                        Category.name.ilike(f"%{search}%"),
                        Category.description.ilike(f"%{search}%")
                    )
                )
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await self.db.execute(count_query)
            total = total_count.scalar() or 0
            
            # Calculate offset
            skip = (page_index - 1) * page_size
            
            # Get paginated data
            query = query.offset(skip).limit(page_size)
            result = await self.db.execute(query)
            categories = result.scalars().all()
            
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": total,
                "data": categories
            }
        except Exception as e:
            return {
                "page_index": page_index,
                "page_size": page_size,
                "count": 0,
                "data": []
            }

    async def get_root_categories(self) -> List[Category]:
        """Get categories without parent (root level)"""
        result = await self.db.execute(
            select(Category)
            .options(selectinload(Category.children))
            .where(and_(Category.parent_id.is_(None), Category.is_active == True))
        )
        return result.scalars().all()

    async def update_category(self, category_id: int, category_data: CategoryUpdate, current_user_id: int) -> Category:
        category = await self.get_category_by_id(category_id)
        if not category:
            raise NotFoundError("Category not found")

        # Check parent validity if being updated
        if category_data.parent_id and category_data.parent_id != category.parent_id:
            if category_data.parent_id == category.id:
                raise ValidationError("Category cannot be its own parent")
            
            parent = await self.get_category_by_id(category_data.parent_id)
            if not parent:
                raise ValidationError("Parent category not found")

        # Check for duplicate name if name is being changed
        if category_data.name and category_data.name != category.name:
            existing = await self.db.execute(
                select(Category).where(and_(
                    Category.name == category_data.name,
                    Category.id != category_id
                ))
            )
            if existing.scalar_one_or_none():
                raise ValidationError("Category name already exists")

        for field, value in category_data.dict(exclude_unset=True).items():
            setattr(category, field, value)
        
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def delete_category(self, category_id: int, current_user_id: int) -> bool:
        category = await self.get_category_by_id(category_id)
        if not category:
            raise NotFoundError("Category not found")

        items_result = await self.db.execute(
            select(Item).where(Item.category_id == category_id).limit(1)
        )
        if items_result.scalar_one_or_none():
            raise ValidationError("Cannot delete category with associated items")

        # Soft delete
        category.is_active = False
        category.is_deleted = True
        await self.db.commit()
        return True