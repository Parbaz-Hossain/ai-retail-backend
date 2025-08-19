from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_
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
            **category_data.dict(),
            created_by=current_user_id,
            updated_by=current_user_id
        )
        
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def get_category_by_id(self, category_id: int) -> Optional[Category]:
        result = await self.db.execute(
            select(Category)
            .options(selectinload(Category.parent), selectinload(Category.children))
            .where(and_(Category.id == category_id, Category.is_active == True))
        )
        return result.scalar_one_or_none()

    async def get_categories(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> List[Category]:
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
        
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

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
        
        category.updated_by = current_user_id
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def delete_category(self, category_id: int, current_user_id: int) -> bool:
        category = await self.get_category_by_id(category_id)
        if not category:
            raise NotFoundError("Category not found")

        # Check if category has items
        from app.models.inventory.item import Item
        items_result = await self.db.execute(
            select(Item).where(Item.category_id == category_id).limit(1)
        )
        if items_result.scalar_one_or_none():
            raise ValidationError("Cannot delete category with associated items")

        # Soft delete
        category.is_active = False
        category.updated_by = current_user_id
        await self.db.commit()
        return True