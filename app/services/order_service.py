from fastapi import HTTPException, status
from sqlalchemy import func

from app.core.exceptions import OrderException
from app.crud.order import OrderCrud


class OrderService:
    def __init__(self, db):
        self.db = db
        self.crud = OrderCrud(db)

    def place_order(self, user_id: int, shipping_id: int, billing_id: int):
        try:
            return self.crud.create_order(user_id, shipping_id, billing_id)
        except OrderException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            )

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

        # Restore stock for each item
        for item in order.order_items:
            product = item.product
            if product:
                product.stock_quantity += item.quantity

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

