from fastapi import HTTPException, status
from sqlalchemy import func

from app.core.exceptions import OrderException
from app.crud.order import OrderCrud
from app.core.redis import redis_client


class OrderService:
    def __init__(self, db):
        self.db = db
        self.crud = OrderCrud(db)

    async def place_order(self, user_id: int, shipping_id: int, billing_id: int):
        lock_key = f"checkout_lock:{user_id}"
        
        # acquire lock for 10 seconds to prevent double submission
        acquired = await redis_client.client.set(lock_key, "1", nx=True, ex=10)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
                detail="Checkout already in progress. Please wait."
            )
            
        try:
            return self.crud.create_order(user_id, shipping_id, billing_id)
        except OrderException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            )
        finally:
            await redis_client.client.delete(lock_key)

    def list_orders(self, user_id: int):
        return self.crud.get_orders(user_id)

    def get_one_order(self, user_id: int, order_id: int):
        try:
            return self.crud.get_order_by_id(user_id, order_id)
        except OrderException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            )

    def cancel_order(self, user_id: int, order_id: int):
        """
        Cancel a pending order and restore product stock.

        Only orders with status 'pending' can be cancelled.

        Raises:
            HTTPException 404 if the order is not found.
            HTTPException 400 if the order cannot be cancelled (already paid/shipped/etc).
        """
        try:
            order = self.crud.get_order_by_id(user_id, order_id)
        except OrderException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            )

        if order.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only pending orders can be cancelled. Current status: '{order.status}'.",
            )

        # Clear reservations for this user
        from app.models.inventory_reservation import InventoryReservation
        reservations = self.db.query(InventoryReservation).filter(
            InventoryReservation.user_id == order.user_id
        ).all()
        for res in reservations:
            self.db.delete(res)

        from app.models.order_event import OrderEvent
        
        event = OrderEvent(
            order_id=order.id,
            from_status=order.status,
            to_status="cancelled",
            note="Order cancelled by user",
            created_by=user_id
        )
        self.db.add(event)

        order.status = "cancelled"
        order.payment_status = "failed"
        order.cancelled_at = func.current_timestamp()
        
        self.db.commit()
        self.db.refresh(order)
        return order

