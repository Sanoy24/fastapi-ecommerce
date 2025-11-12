from pydantic import BaseModel

# class Category(Base):
#     __tablename__ = "categories"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     name = Column(String(20), unique=True)
#     slug = Column(String(20), unique=True)
#     parent_id = Column(Integer, ForeignKey("categories.id"))
#     description = Column(Text)
#     image_url = Column(String(30))

#     # Relationships (self-referential)
#     parent = relationship("Category", remote_side=[id], back_populates="children")
#     children = relationship("Category", back_populates="parent")
#     products = relationship("Product", back_populates="category")


class CreateCategory(BaseModel):
    name: str
    slug: str
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = None


class CategoryPublic(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class UpdateCategory(BaseModel):
    name: str | None = None
    slug: str | None = None
    parent_id: int | None = None
    description: str | None = None
    image_url: str | None = None