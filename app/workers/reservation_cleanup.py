import asyncio
from datetime import datetime, timezone
import logging
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.inventory_reservation import InventoryReservation

logger = logging.getLogger(__name__)

async def cleanup_expired_reservations_loop():
    """Background loop to periodically delete expired InventoryReservation rows."""
    while True:
        try:
            # Run cleanup every 5 minutes
            await asyncio.sleep(300)

            db: Session = SessionLocal()
            try:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                expired = db.query(InventoryReservation).filter(
                    InventoryReservation.expires_at < now
                ).all()
                count = len(expired)
                if count > 0:
                    for r in expired:
                        db.delete(r)
                    db.commit()
                    logger.info(f"Cleaned up {count} expired inventory reservations.")
            except Exception as e:
                db.rollback()
                logger.error(f"Error cleaning up reservations: {e}")
            finally:
                db.close()

        except asyncio.CancelledError:
            logger.info("Reservation cleanup task cancelled.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in reservation cleanup loop: {e}")
