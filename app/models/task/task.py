from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Enum as SQLEnum, Date, Time, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import BaseModel
from app.models.shared.enums import TaskStatus, TaskPriority

class Task(BaseModel):
    __tablename__ = 'tasks'
    
    task_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    task_type_id = Column(Integer, ForeignKey('task_types.id'), nullable=False)
    
    # Task context (what triggered this task)
    reference_type = Column(String(50))  # INVENTORY_LOW_STOCK, REORDER_REQUEST, SALARY_GENERATION, etc.
    reference_id = Column(Integer)  # ID of the related record
    reference_data = Column(JSON)  # Additional context data
    
    # Assignment and ownership
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    assigned_to = Column(Integer, ForeignKey('users.id'))
    department_id = Column(Integer, ForeignKey('departments.id'))
    location_id = Column(Integer, ForeignKey('locations.id'))
    
    # Status and priority
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    priority = Column(SQLEnum(TaskPriority), default=TaskPriority.MEDIUM)
    
    # Dates
    due_date = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Additional fields
    estimated_hours = Column(Numeric(4, 2))
    actual_hours = Column(Numeric(4, 2))
    tags = Column(String(500))  # Comma-separated tags
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(100))  # DAILY, WEEKLY, MONTHLY
    parent_task_id = Column(Integer, ForeignKey('tasks.id'))  # For sub-tasks
    
    # Auto-assignment rules
    auto_assigned = Column(Boolean, default=False)
    escalation_level = Column(Integer, default=0)
    escalated_at = Column(DateTime(timezone=True))
    
    is_active = Column(Boolean, default=True)
    
    # Relationships
    task_type = relationship("TaskType", back_populates="tasks")
    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    department = relationship("Department")
    location = relationship("Location")
    parent_task = relationship("Task", remote_side="Task.id", back_populates="sub_tasks")
    sub_tasks = relationship("Task", back_populates="parent_task")
    assignments = relationship("TaskAssignment", back_populates="task")
    comments = relationship("TaskComment", back_populates="task")
    attachments = relationship("TaskAttachment", back_populates="task")