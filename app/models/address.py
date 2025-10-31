from sqlalchemy import Column, Integer, ForeignKey, Text, String, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type = Column(String(20), nullable=False)
    street = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))
    is_default = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="addresses")
