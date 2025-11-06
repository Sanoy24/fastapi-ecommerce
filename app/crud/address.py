from app.models.address import Address
from sqlalchemy.orm import Session
from app.schema.address_schema import AddressCreate, AddressUpdate, AddressPublic


class AddressCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_address(self, id: int, address_data: AddressCreate) -> Address:
        """
        Create a new address
        """
        db_address = Address(**address_data.model_dump(), user_id=id)
        self.db.add(db_address)
        self.db.commit()
        self.db.refresh(db_address)
        return db_address

    def update_address(self, address_id: int, address_data: AddressUpdate) -> Address:
        """
        Update an existing address
        """
        db_address = self.db.query(Address).filter(Address.id == address_id).first()
        if not db_address:
            return None
        for key, value in address_data.model_dump(exclude_unset=True).items():
            setattr(db_address, key, value)
        self.db.commit()
        self.db.refresh(db_address)
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
