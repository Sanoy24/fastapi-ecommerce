from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import HTTPException, status

from app.models.user import User
from app.models.order import Order
from app.models.product import Product
from app.models.review import Review
from app.crud.order import OrderCrud
from app.crud.user import UserCrud
from app.crud.product import ProductCrud
from app.crud.review import ReviewCrud
from app.schema.admin_schema import (
    SalesAnalytics,
    UserAnalytics,
    ProductAnalytics,
    ReviewAnalytics,
    DashboardOverview,
    UserListItem,
    UserManagementResponse,
    OrderListItem,
    OrderManagementResponse,
    ReviewModerationItem,
    ReviewModerationResponse,
    InventoryAlert,
    BulkInventoryUpdateItem,
    BulkInventoryUpdateResponse,
)


class AdminService:
    """Service layer for admin dashboard and management operations"""

    def __init__(self, db: Session):
        self.db = db
        self.order_crud = OrderCrud(db=db)
        self.user_crud = UserCrud(db=db)
        self.product_crud = ProductCrud(db=db)
        self.review_crud = ReviewCrud(db=db)

    # Analytics Methods
    def get_sales_analytics(self) -> SalesAnalytics:
        """Calculate sales analytics including revenue and order statistics"""
        # Total orders and revenue
        total_orders = self.order_crud.get_total_orders()
        total_revenue = self.order_crud.get_total_revenue()

        # Orders by status
        pending_orders = self.order_crud.get_pending_orders()
        paid_orders = self.order_crud.get_paid_orders()
        shipped_orders = self.order_crud.get_shipped_orders_count()
        delivered_orders = self.order_crud.get_delivered_orders_count()
        cancelled_orders = self.order_crud.get_cancelled_orders_count()

        # Average order value
        average_order_value = (
            round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0
        )

        # Revenue last 30 days
        revenue_last_30_days = self.order_crud.revenue_last_thirty_days()

        return SalesAnalytics(
            total_revenue=float(total_revenue),
            total_orders=total_orders,
            pending_orders=pending_orders,
            paid_orders=paid_orders,
            shipped_orders=shipped_orders,
            delivered_orders=delivered_orders,
            cancelled_orders=cancelled_orders,
            average_order_value=average_order_value,
            revenue_last_30_days=float(revenue_last_30_days),
        )

    def get_user_analytics(self) -> UserAnalytics:
        """Calculate user analytics including total users and growth"""
        total_users = self.user_crud.get_total_users()
        total_customers = self.user_crud.get_total_customers()
        total_admins = self.user_crud.get_total_admins()
        # New users in last 30 days
        new_users_last_30_days = self.user_crud.get_new_user_in_last_thirty_days()

        return UserAnalytics(
            total_users=total_users,
            total_customers=total_customers,
            total_admins=total_admins,
            new_users_last_30_days=new_users_last_30_days,
        )

    def get_product_analytics(self) -> ProductAnalytics:
        """Calculate product analytics including inventory status"""
        total_products = self.product_crud.get_total_products()
        active_products = self.product_crud.total_active_products()
        inactive_products = self.product_crud.total_inactive_products()
        out_of_stock_count = self.product_crud.out_of_stock_count()
        low_stock_count = self.product_crud.low_stock_count()

        return ProductAnalytics(
            total_products=total_products,
            active_products=active_products,
            inactive_products=inactive_products,
            out_of_stock_count=out_of_stock_count,
            low_stock_count=low_stock_count,
        )

    def get_review_analytics(self) -> ReviewAnalytics:
        """Calculate review analytics including approval status"""
        total_reviews = self.review_crud.total_reviews()
        pending_reviews = self.review_crud.pending_reviews()
        approved_reviews = self.review_crud.approved_reviews()
        average_rating = self.review_crud.average_rating()

        return ReviewAnalytics(
            total_reviews=total_reviews,
            pending_reviews=pending_reviews,
            approved_reviews=approved_reviews,
            average_rating=round(float(average_rating), 2) if average_rating else None,
        )

    def get_dashboard_overview(self) -> DashboardOverview:
        """Get complete dashboard overview with all analytics"""
        return DashboardOverview(
            sales=self.get_sales_analytics(),
            users=self.get_user_analytics(),
            products=self.get_product_analytics(),
            reviews=self.get_review_analytics(),
        )

    # User Management Methods
    def get_all_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
    ) -> UserManagementResponse:
        """Get paginated list of all users with optional filters"""
        # query = self.db.query(User)

        # # Apply filters
        # if search:
        #     search_filter = or_(
        #         User.email.ilike(f"%{search}%"),
        #         User.first_name.ilike(f"%{search}%"),
        #         User.last_name.ilike(f"%{search}%"),
        #     )
        #     query = query.filter(search_filter)

        # if role:
        #     query = query.filter(User.role == role)

        # # Get total count
        # total = query.count()

        # # Apply pagination
        # offset = (page - 1) * page_size
        # users = query.offset(offset).limit(page_size).all()
        total, users = self.user_crud.get_all_users(page, page_size, search, role)

        # Build user list with additional stats
        user_items = []
        for user in users:
            # Calculate total orders and spent
            total_orders = self.order_crud.total_order_by_user(user.id)
            total_spent = self.order_crud.total_spent_by_user(user.id)

            user_items.append(
                UserListItem(
                    id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    role=user.role,
                    created_at=user.created_at,
                    total_orders=total_orders,
                    total_spent=float(total_spent),
                )
            )

        return UserManagementResponse(
            users=user_items, total=total, page=page, page_size=page_size
        )

    def update_user_role(self, user_id: int, new_role: str) -> User:
        """Update a user's role"""
        if new_role not in ["customer", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Must be 'customer' or 'admin'",
            )

        user = self.user_crud.update_user_role(user_id, new_role)
        return user

    # Order Management Methods
    def get_all_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> OrderManagementResponse:
        """Get paginated list of all orders with optional filters"""
        total, orders = self.order_crud.get_all_orders(page, page_size, status)
        order_items = []
        for order in orders:
            order_items.append(
                OrderListItem(
                    id=order.id,
                    order_number=order.order_number,
                    user_id=order.user_id,
                    user_email=order.user.email,
                    total_amount=float(order.total_amount),
                    status=order.status,
                    payment_status=order.payment_status,
                    order_date=order.order_date,
                    shipped_at=order.shipped_at,
                )
            )

        return OrderManagementResponse(
            orders=order_items, total=total, page=page, page_size=page_size
        )

    def update_order_status(self, order_id: int, new_status: str) -> Order:
        """Update an order's status"""
        valid_statuses = ["pending", "paid", "shipped", "delivered", "cancelled"]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )

        return self.order_crud.update_order_status(order_id, new_status)

    def mark_order_shipped(
        self, order_id: int, shipped_at: Optional[datetime] = None
    ) -> Order:
        """Mark an order as shipped"""
        return self.order_crud.mark_order_shipped(order_id, shipped_at)

    # Review Moderation Methods
    def get_pending_reviews(
        self, page: int = 1, page_size: int = 20
    ) -> ReviewModerationResponse:
        """Get paginated list of pending reviews"""
        total, reviews = self.review_crud.get_pending_reviews(page, page_size)

        review_items = []
        for review in reviews:
            review_items.append(
                ReviewModerationItem(
                    id=review.id,
                    user_id=review.user_id,
                    user_email=review.user.email,
                    product_id=review.product_id,
                    product_name=review.product.name,
                    rating=review.rating,
                    comment=review.comment,
                    created_at=review.created_at,
                    is_approved=review.is_approved,
                )
            )

        return ReviewModerationResponse(
            reviews=review_items, total=total, page=page, page_size=page_size
        )

    def get_all_reviews(
        self, page: int = 1, page_size: int = 20
    ) -> ReviewModerationResponse:
        """Get paginated list of all reviews"""
        total, reviews = self.review_crud.get_all_reviews(page, page_size)

        review_items = []
        for review in reviews:
            review_items.append(
                ReviewModerationItem(
                    id=review.id,
                    user_id=review.user_id,
                    user_email=review.user.email,
                    product_id=review.product_id,
                    product_name=review.product.name,
                    rating=review.rating,
                    comment=review.comment,
                    created_at=review.created_at,
                    is_approved=review.is_approved,
                )
            )

        return ReviewModerationResponse(
            reviews=review_items, total=total, page=page, page_size=page_size
        )

    def approve_review(self, review_id: int) -> Review:
        """Approve a review"""
        return self.review_crud.approve_review(review_id)

    def reject_review(self, review_id: int) -> None:
        """Reject/delete a review"""
        return self.review_crud.reject_review(review_id)

    # Inventory Management Methods
    def get_low_stock_products(self, threshold: int = 10) -> List[InventoryAlert]:
        """Get products with low stock"""
        products = self.product_crud.get_slow_stock_products(threshold)

        return [
            InventoryAlert(
                id=p.id,
                name=p.name,
                sku=p.sku,
                stock_quantity=p.stock_quantity,
                is_active=p.is_active,
            )
            for p in products
        ]

    def bulk_update_inventory(
        self, updates: List[BulkInventoryUpdateItem]
    ) -> BulkInventoryUpdateResponse:
        """Bulk update product inventory"""
        updated_count, failed_products = self.product_crud.bulk_update_inventory(
            updates
        )

        return BulkInventoryUpdateResponse(
            updated_count=updated_count, failed_products=failed_products
        )
