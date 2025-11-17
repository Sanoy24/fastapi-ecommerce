from sqlalchemy import select
from app.models.address import Address
from sqlalchemy.orm import Session
from app.schema.address_schema import AddressCreate, AddressUpdate, AddressPublic
from app.core.logger import logger


class AddressCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_address(
        self, id: int, is_first: bool, address_data: AddressCreate
    ) -> Address:
        """
        Create a new address
        """
        data = address_data.model_dump()
        if is_first:
            data["is_default"] = True

        db_address = Address(**data, user_id=id)
        self.db.add(db_address)
        self.db.commit()
        self.db.refresh(db_address)
        return db_address

    def update_defualt_address(self, user_id: int):
        """
        Update default address for a user
        """
        self.db.query(Address).filter(
            Address.user_id == user_id, Address.is_default == True
        ).update({"is_default": False})
        self.db.commit()

    def get_single_address(self, address_id: int) -> Address:
        """
        Get a single address by ID
        """
        db_address = self.db.query(Address).filter(Address.id == address_id).first()
        return db_address

    def delete_address(self, address_id: int) -> bool:
        """
        Delete an address by ID
        """
        db_address = self.db.query(Address).filter(Address.id == address_id).first()
        if not db_address:
            return False
        self.db.delete(db_address)
        self.db.commit()
        return True
