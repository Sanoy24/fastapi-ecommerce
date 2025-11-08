from fastapi import APIRouter, Depends, HTTPException, status
from app.db.database import check_db_health
from sqlalchemy.orm import Session
from app.dependencies import get_db
from pydantic import BaseModel

router = APIRouter(tags={"Healthcheck"})


class HealthCheckResponseModel(BaseModel):
    status: str
    database: str


@router.get("", response_model=HealthCheckResponseModel)
async def health_check(db: Session = Depends(get_db)):
    """
    Endpoint to check the health status of the database connection and overall server.
    """
    if check_db_health(db):
        return {"status": "ok", "database": "Database status is healthy"}
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service unhealthy"
        )
