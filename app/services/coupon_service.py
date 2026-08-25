from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.crud.coupon_crud import CouponCrud
from app.schema.coupon_schema import CouponCreate, CouponUpdate, CouponPublic
from typing import List

class CouponService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = CouponCrud(db)

    def create_coupon(self, coupon_data: CouponCreate) -> CouponPublic:
        existing = self.crud.get_coupon_by_code(coupon_data.code)
        if existing:
            raise HTTPException(status_code=400, detail="Coupon code already exists.")

        coupon = self.crud.create_coupon(coupon_data)
        return CouponPublic.model_validate(coupon)

    def get_coupon(self, coupon_id: int) -> CouponPublic:
        coupon = self.crud.get_coupon_by_id(coupon_id)
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
        return CouponPublic.model_validate(coupon)

    def get_coupon_by_code(self, code: str) -> CouponPublic:
        coupon = self.crud.get_coupon_by_code(code)
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
        return CouponPublic.model_validate(coupon)

    def list_coupons(self, skip: int = 0, limit: int = 100) -> List[CouponPublic]:
        coupons = self.crud.list_coupons(skip=skip, limit=limit)
        return [CouponPublic.model_validate(c) for c in coupons]

    def update_coupon(self, coupon_id: int, coupon_data: CouponUpdate) -> CouponPublic:
        coupon = self.crud.get_coupon_by_id(coupon_id)
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")

        if coupon_data.code and coupon_data.code != coupon.code:
            existing = self.crud.get_coupon_by_code(coupon_data.code)
            if existing:
                raise HTTPException(status_code=400, detail="Coupon code already exists.")

        updated_coupon = self.crud.update_coupon(coupon, coupon_data)
        return CouponPublic.model_validate(updated_coupon)

    def delete_coupon(self, coupon_id: int) -> None:
        coupon = self.crud.get_coupon_by_id(coupon_id)
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
        self.crud.delete_coupon(coupon)
