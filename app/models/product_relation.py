from sqlalchemy import Boolean, ForeignKey, Enum as SQLEnum, text
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
    # True for rows written by compute_frequently_bought_together_task
    # (see app/workers/arq_worker.py) from real co-purchase history rather
    # than entered by an admin. The cron only ever adds/removes rows where
    # this is True, so a manually curated relation — even one of type
    # frequently_bought_together — is never touched by the recompute.
    is_auto_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    related_product: Mapped["Product"] = relationship("Product", foreign_keys=[related_product_id])
