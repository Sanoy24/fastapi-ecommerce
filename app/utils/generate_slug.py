from slugify import slugify
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.product import Product
from app.models.category import Category
from app.core.logger import logger
from typing import Literal, Set
import uuid

SlugContext = Literal["product", "category"]


def generate_slug(db: Session, name: str, context: SlugContext) -> str:
    """
    Generates a unique slug for a given name and context (model).
    """
    if context == "product":
        Model = Product
    elif context == "category":
        Model = Category
    else:
        raise ValueError(f"Invalid slug context: {context}")

    base_slug = slugify(name, lowercase=True)

    stmt = select(Model.slug).where(Model.slug.like(f"{base_slug}%"))
    existing_slugs: Set[str] = set(db.scalars(stmt).all())

    if base_slug not in existing_slugs:
        return base_slug

    counter = 1
    while f"{base_slug}-{counter}" in existing_slugs:
        counter += 1

    return f"{base_slug}-{counter}"


def generate_sku(name: str, prefix: str = "PRD") -> str:
    """Generate SKU from product name + random suffix."""
    base = slugify(name, separator="", lowercase=False)[:5].upper()
    unique_part = uuid.uuid4().hex[:4].upper()
    return f"{prefix}-{base}-{unique_part}"
