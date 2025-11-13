from slugify import slugify
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.product import Product
from app.core.logger import logger
import uuid


def generate_slug(db: Session, name: str):
    base_slug = slugify(name, lowercase=True)
    stmt = select(Product.slug).where(Product.slug.like(f"{base_slug}%"))
    existing_slugs = set(db.scalars(stmt).all())

    if base_slug not in existing_slugs:
        return base_slug

    counter = 1

    while f"{base_slug}-{counter}" in existing_slugs:
        counter += 1
    logger.info(f"final count: {counter}")
    return f"{base_slug}-{counter}"


def generate_sku(name: str, prefix: str = "PRD") -> str:
    """Generate SKU from product name + random suffix."""
    base = slugify(name, separator="", lowercase=False)[:5].upper()
    unique_part = uuid.uuid4().hex[:4].upper()
    return f"{prefix}-{base}-{unique_part}"
