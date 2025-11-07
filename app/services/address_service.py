from sqlalchemy.orm import Session
from app.crud.address import AddressCrud
from app.schema.address_schema import AddressCreate, AddressPublic, AddressUpdate
from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from app.models.address import Address


class AddressService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = AddressCrud(db=db)

    def add_address(
        self, user_id: int, is_first: bool, address_data: AddressCreate
    ) -> AddressPublic:
        address = self.crud.create_address(user_id, is_first, address_data)
        return AddressPublic.model_validate(address)

    def update_address(
        self, address_id: int, address_data: AddressUpdate
    ) -> AddressPublic:
        address = self.crud.get_single_address(address_id)
        if not address:
            raise HTTPException(status_code=s, detail="Address not found")
        update_address_data = address_data.model_dump(exclude_unset=True)
        try:
            if update_address_data.get("is_default"):
                self.crud.update_defualt_address(address.user_id)
            for key, value in update_address_data.items():
                setattr(address, key, value)
            self.db.commit()
            self.db.refresh(address)
            return AddressPublic.model_validate(address)

        except Exception as e:
            raise HTTPException(status_code=400, detail=e.errors())
