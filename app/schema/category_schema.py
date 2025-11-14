from pydantic import BaseModel, Field, field_validator, ValidationInfo, HttpUrl
from app.core.logger import logger
import re

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
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: int | None = None
    description: str | None = None
    image_url: HttpUrl | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Electronics",
                    "parent_id": 1,
                    "description": "Electronics products",
                    "image_url": "https://images.com",
                }
            ]
        }
    }

    # @field_validator("slug")
    # def validate_slug(cls, v):
    #     if not v.islower() or not re.match(r"^[a-z0-9-]+$", v):
    #         raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
    #     return v

    # @field_validator("image_url")
    # def validate_image_url(cls, v):
    #     if v and not v.startswith(("http://", "https://")):
    #         raise ValueError("Image URL must be a valid HTTP/HTTPS link")
    #     return v

    @field_validator("parent_id")
    def prevent_self_parent(cls, v, info: ValidationInfo):
        # `info.data` contains already validated fields
        logger.info(f"-- validation result ---: {info.data}")
        if v is not None and "id" in info.data and v == info.data["id"]:
            raise ValueError("Category cannot be its own parent")
        return v


class CategoryPublic(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: int | None = None
    description: str | None = None
    image_url: HttpUrl | None = None

    model_config = {"from_attributes": True}


class UpdateCategory(BaseModel):
    name: str | None = None
    slug: str | None = None
    parent_id: int | None = None
    description: str | None = None
    image_url: HttpUrl | None = None

    @field_validator("slug")
    def validate_slug(cls, v):
        if not v.islower() or not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v

    @field_validator("image_url")
    def validate_image_url(cls, v):
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Image URL must be a valid HTTP/HTTPS link")
        return v

    model_config = {"from_attributes": True}
