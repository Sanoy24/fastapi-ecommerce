from sqlalchemy.orm import Session
from app.crud.address import AddressCrud
from app.schema.address_schema import AddressCreate, AddressPublic


class AddressService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = AddressCrud(db=db)

    def add_address(self, user_id: int, address_data: AddressCreate) -> AddressPublic:
        address = self.crud.create_address(user_id, address_data)
        # Here you would typically associate the address with the user in the database
        return AddressPublic.model_validate(address)
