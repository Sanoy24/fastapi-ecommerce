from sqlalchemy import Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class ProductRelation(Base):
    __tablename__ = "product_relations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    related_product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(
        SQLEnum("similar", "frequently_bought_together", "accessory", name="product_relation_type"),
        default="similar"
    )

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    related_product: Mapped["Product"] = relationship("Product", foreign_keys=[related_product_id])
