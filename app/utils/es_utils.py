from decimal import Decimal

from elasticsearch import AsyncElasticsearch, helpers
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.logger import logger
from app.db.database import SessionLocal
from app.models.product import Product


async def create_product_index(es: AsyncElasticsearch):
    """create product index"""
    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "english": {"type": "text", "analyzer": "english"},
                    },
                },
                "description": {"type": "text"},
                "category": {"type": "keyword"},
                "price": {"type": "float"},
                "in_stock": {"type": "boolean"},
                "suggest": {
                    "type": "completion",
                    "contexts": [{"name": "category", "type": "category"}],
                },
            }
        }
    }

    if await es.indices.exists(index="products"):
        await es.indices.delete(index="products")
        print("Deleted old 'products' index")

    await es.indices.create(index="products", body=mapping)
    print("Created fresh 'products' index")


def get_all_products():
    with SessionLocal() as db:
        stmt = select(Product).options(selectinload(Product.category))
        return db.scalars(stmt).all()


async def bulk_index_products(es: AsyncElasticsearch):
    """populate elastic index from existing products"""
    products = get_all_products()
    print(products[0])

    actions = []

    for p in products:
        actions.append(
            {
                "_index": "products",
                "_id": p.id,
                "_source": {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "category": p.category.name if p.category else None,
                    "price": (
                        float(p.price) if isinstance(p.price, Decimal) else p.price
                    ),
                    "in_stock": p.in_stock,
                    "suggest": {
                        "input": [p.name],
                        "contexts": {
                            "category": (
                                [p.category.name] if p.category else ["General"]
                            )
                            + ["all"]
                        },
                    },
                },
            }
        )
    await helpers.async_bulk(es, actions=actions)
    logger.info(f"Indexed {len(actions)} products into Elasticsearch!")
