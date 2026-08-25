from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from typing import List

from app.db.database import get_db
from app.models.tax_rate import TaxRate
from app.schema.tax_schema import TaxRateCreate, TaxRateUpdate, TaxRateResponse
from app.dependencies import get_current_admin_user
from app.models.user import User
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin/tax-rates", tags=["tax-rates"])

@router.get("/", response_model=List[TaxRateResponse])
def list_tax_rates(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    stmt = select(TaxRate)
    return db.scalars(stmt).all()

@router.post("/", response_model=TaxRateResponse, status_code=status.HTTP_201_CREATED)
def create_tax_rate(
    data: TaxRateCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    admin_service = AdminService(db=db)
    
    tax_rate = TaxRate(**data.model_dump())
    db.add(tax_rate)
    db.commit()
    db.refresh(tax_rate)
    
    # Log action
    admin_service.log_action(
        admin_id=admin.id,
        action="CREATE_TAX_RATE",
        resource_type="tax_rate",
        resource_id=tax_rate.id,
        new_value=data.model_dump()
    )
    
    return tax_rate

@router.put("/{id}", response_model=TaxRateResponse)
def update_tax_rate(
    id: int,
    data: TaxRateUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    admin_service = AdminService(db=db)
    tax_rate = db.get(TaxRate, id)
    if not tax_rate:
        raise HTTPException(status_code=404, detail="Tax rate not found")
        
    old_value = {
        "name": tax_rate.name,
        "rate": float(tax_rate.rate),
        "applies_to": tax_rate.applies_to,
        "category_id": tax_rate.category_id,
        "region": tax_rate.region,
        "is_active": tax_rate.is_active
    }
    
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(tax_rate, k, v)
        
    db.commit()
    db.refresh(tax_rate)
    
    admin_service.log_action(
        admin_id=admin.id,
        action="UPDATE_TAX_RATE",
        resource_type="tax_rate",
        resource_id=tax_rate.id,
        old_value=old_value,
        new_value=update_data
    )
    
    return tax_rate

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tax_rate(
    id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user)
):
    admin_service = AdminService(db=db)
    tax_rate = db.get(TaxRate, id)
    if not tax_rate:
        raise HTTPException(status_code=404, detail="Tax rate not found")
        
    db.delete(tax_rate)
    db.commit()
    
    admin_service.log_action(
        admin_id=admin.id,
        action="DELETE_TAX_RATE",
        resource_type="tax_rate",
        resource_id=id
    )
