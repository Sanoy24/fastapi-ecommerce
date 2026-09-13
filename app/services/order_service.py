import secrets

from fastapi import HTTPException, status
from sqlalchemy import func

from app.core.exceptions import OrderException
from app.crud.order import OrderCrud
from app.core.redis import redis_client
from app.schema.order_schema import GuestAddressInput

# Mirrors UserService's password-reset token pattern exactly (same TTL
# style, same Redis prefix style): a random urlsafe token maps to the
# resource it authorizes, expires on its own, and is deleted the moment
# it's used.
_GUEST_CLAIM_TOKEN_PREFIX = "guest_order_claim:"
_GUEST_CLAIM_TOKEN_TTL = 30 * 24 * 3600  # 30 days


class OrderService:
    def __init__(self, db):
        self.db = db
        self.crud = OrderCrud(db)

    async def place_order(self, user_id: int, shipping_id: int, billing_id: int, shipping_method_id: int | None = None):
        lock_key = f"checkout_lock:{user_id}"

        # acquire lock for 10 seconds to prevent double submission
        acquired = await redis_client.client.set(lock_key, "1", nx=True, ex=10)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Checkout already in progress. Please wait."
            )

        try:
            return self.crud.create_order(user_id, shipping_id, billing_id, shipping_method_id)
        except OrderException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            )
        finally:
            await redis_client.client.delete(lock_key)

    async def place_guest_order(
        self,
        session_id: str,
        guest_email: str,
        shipping_address: GuestAddressInput,
        billing_address: GuestAddressInput,
        shipping_method_id: int | None = None,
    ):
        lock_key = f"checkout_lock:guest:{session_id}"

        acquired = await redis_client.client.set(lock_key, "1", nx=True, ex=10)
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Checkout already in progress. Please wait."
            )

        try:
            return self.crud.create_guest_order(
                session_id, guest_email, shipping_address, billing_address, shipping_method_id
            )
        except OrderException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            )
        finally:
            await redis_client.client.delete(lock_key)

    def lookup_guest_order(self, order_number: str, email: str):
        """Used for both the guest order-status lookup endpoint and, after
        checkout, letting a guest check their own order without an account.
        """
        order = self.crud.get_guest_order_by_number_and_email(order_number, email)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order

    async def request_guest_order_claim_link(
        self, order_number: str, email: str, arq_pool=None
    ) -> None:
        """
        Email a one-time link that attaches a guest order to an account.

        Always returns success regardless of whether anything matched — the
        same anti-enumeration shape as UserService.forgot_password. The
        token is the entire authorization for claim_guest_order below, by
        design: it proves whoever clicks it received the email at
        guest_email, which is a deliberately lower bar than requiring the
        claiming account's own email to match (someone may reasonably want
        to save an order placed with a work email into a personal account).
        """
        order = self.crud.get_guest_order_by_number_and_email(order_number, email)
        if not order:
            return

        token = secrets.token_urlsafe(32)
        await redis_client.client.setex(
            f"{_GUEST_CLAIM_TOKEN_PREFIX}{token}", _GUEST_CLAIM_TOKEN_TTL, str(order.id)
        )

        if arq_pool:
            await arq_pool.enqueue_job(
                "send_guest_order_claim_email_task", email, order.order_number, token
            )
        else:
            from app.services.email_service import send_guest_order_claim_email
            await send_guest_order_claim_email(
                to_address=email, order_number=order.order_number, claim_token=token
            )

    async def claim_guest_order(self, claim_token: str, user_id: int):
        """Attach a guest order to the calling (authenticated) account.

        One-time use: the token is deleted whether the claim succeeds or
        the order turns out to already be claimed, so a token can't be
        replayed after either outcome.
        """
        redis_key = f"{_GUEST_CLAIM_TOKEN_PREFIX}{claim_token}"
        order_id_str = await redis_client.client.get(redis_key)
        if not order_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired claim link.",
            )

        from app.models.order import Order
        order = self.db.get(Order, int(order_id_str))
        await redis_client.client.delete(redis_key)

        if not order or order.user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This order has already been claimed or no longer exists.",
            )

        order.user_id = user_id
        self.db.commit()
        self.db.refresh(order)
        return order

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

        # Clear this order's reservations. Filtering by order_id, not
        # user_id: user_id == order.user_id would also match this user's
        # OTHER simultaneous pending orders' reservations (or, for a guest
        # order where user_id is None, every other guest order's
        # reservations, since they'd all share user_id IS NULL) — deleting
        # those early would let their stock be resold before they've
        # actually been paid for or cancelled.
        from app.models.inventory_reservation import InventoryReservation
        reservations = self.db.query(InventoryReservation).filter(
            InventoryReservation.order_id == order.id
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

        # Only pending orders reach this point (checked above), and payment
        # never succeeds before "paid" — so points_earned is always still 0
        # here; only a redemption needs restoring, never a clawback.
        if order.points_redeemed > 0:
            from app.models.loyalty_transaction import LoyaltyTransaction
            from app.models.user import User

            user = self.db.get(User, user_id)
            if user:
                user.loyalty_points_balance += order.points_redeemed
                self.db.add(LoyaltyTransaction(
                    user_id=user_id,
                    order_id=order.id,
                    points=order.points_redeemed,
                    transaction_type="reversal",
                    note=f"Points redeemed on order {order.order_number} restored after cancellation",
                ))

        order.status = "cancelled"
        order.payment_status = "failed"
        order.cancelled_at = func.current_timestamp()

        self.db.commit()
        self.db.refresh(order)
        return order

