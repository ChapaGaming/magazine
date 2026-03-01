from sqlmodel import SQLModel, Field, select, Relationship
from sqlalchemy import Column, Integer, ForeignKey  # 👈 для ondelete
from sqlalchemy.orm import Mapped  # 👈 для relationship
from typing import Optional, Annotated, List
from datetime import datetime, timedelta

class Users(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    fio: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    admin: bool = Field(default=False)
 
    user_promises: List["Promises"] = Relationship(back_populates="promise_owner")

class Things(SQLModel, table=True):
    __tablename__ = "things"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = Field(unique=True)
    amount: int
    buy_cost: float
    kind: str
    
    thing_requests: List["Promises"] = Relationship(back_populates="requested_thing")

class Promises(SQLModel, table=True):
    __tablename__ = "promises"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    created_at: Optional[datetime] = Field(default=None)
    die_at: Optional[datetime] = Field(default=None)

    priority: str = Field(default="Средний")
    status: str = Field(default="На рассмотрении")
    message: Optional[str] = Field(default=None)

    new_name: Optional[str] = Field(default=None)
    new_description: Optional[str] = Field(default=None)
    new_amount: Optional[int] = Field(default=None)
    new_buy_cost: Optional[float] = Field(default=None)
    new_kind: Optional[str] = Field(default=None)
    
    old_name: Optional[str] = Field(default=None)
    old_description: Optional[str] = Field(default=None)
    old_amount: Optional[int] = Field(default=None)
    old_buy_cost: Optional[float] = Field(default=None)
    old_kind: Optional[str] = Field(default=None)

    # ✅ ИСПРАВЛЕНО (Вариант 1)
    user_id: Optional[int] = Field(
        default=None, 
        foreign_key="users.id",
        #sa_column_kwargs={"ondelete": "CASCADE"}
    )
    thing_id: Optional[int] = Field(
        default=None, 
        foreign_key="things.id",
        #sa_column_kwargs={"ondelete": "CASCADE"}
    )
    
    # ✅ ПРАВИЛЬНО
    promise_owner: Optional["Users"] = Relationship(back_populates="user_promises")
    requested_thing: Optional["Things"] = Relationship(back_populates="thing_requests")