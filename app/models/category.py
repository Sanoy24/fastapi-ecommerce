from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(20), unique=True, nullable=False)
    slug = Column(String(20), unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"))
    description = Column(Text)
    image_url = Column(String(30))

    # Relationships (self-referential)
    parent = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship("Category", back_populates="parent")
    products = relationship("Product", back_populates="category")
