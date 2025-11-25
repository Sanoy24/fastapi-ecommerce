from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import HTTPException, status

from app.models.user import User
from app.models.order import Order
from app.models.product import Product
from app.models.review import Review
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

    # Analytics Methods
    def get_sales_analytics(self) -> SalesAnalytics:
        """Calculate sales analytics including revenue and order statistics"""
        # Total orders and revenue
        total_orders = self.db.query(func.count(Order.id)).scalar() or 0
        total_revenue = self.db.query(func.sum(Order.total_amount)).scalar() or 0.0

        # Orders by status
        pending_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "pending")
            .scalar()
            or 0
        )
        paid_orders = (
            self.db.query(func.count(Order.id)).filter(Order.status == "paid").scalar()
            or 0
        )
        shipped_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "shipped")
            .scalar()
            or 0
        )
        delivered_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "delivered")
            .scalar()
            or 0
        )
        cancelled_orders = (
            self.db.query(func.count(Order.id))
            .filter(Order.status == "cancelled")
            .scalar()
            or 0
        )

        # Average order value
        average_order_value = (
            round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0
        )

        # Revenue last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        revenue_last_30_days = (
            self.db.query(func.sum(Order.total_amount))
            .filter(Order.order_date >= thirty_days_ago)
            .scalar()
            or 0.0
        )

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
        total_users = self.db.query(func.count(User.id)).scalar() or 0
        total_customers = (
            self.db.query(func.count(User.id)).filter(User.role == "customer").scalar()
            or 0
        )
        total_admins = (
            self.db.query(func.count(User.id)).filter(User.role == "admin").scalar()
            or 0
        )

        # New users in last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        new_users_last_30_days = (
            self.db.query(func.count(User.id))
            .filter(User.created_at >= thirty_days_ago)
            .scalar()
            or 0
        )

        return UserAnalytics(
            total_users=total_users,
            total_customers=total_customers,
            total_admins=total_admins,
            new_users_last_30_days=new_users_last_30_days,
        )

    def get_product_analytics(self) -> ProductAnalytics:
        """Calculate product analytics including inventory status"""
        total_products = self.db.query(func.count(Product.id)).scalar() or 0
        active_products = (
            self.db.query(func.count(Product.id))
            .filter(Product.is_active == True)
            .scalar()
            or 0
        )
        inactive_products = (
            self.db.query(func.count(Product.id))
            .filter(Product.is_active == False)
            .scalar()
            or 0
        )
        out_of_stock_count = (
            self.db.query(func.count(Product.id))
            .filter(Product.stock_quantity == 0)
            .scalar()
            or 0
        )
        low_stock_count = (
            self.db.query(func.count(Product.id))
            .filter(and_(Product.stock_quantity > 0, Product.stock_quantity < 10))
            .scalar()
            or 0
        )

        return ProductAnalytics(
            total_products=total_products,
            active_products=active_products,
            inactive_products=inactive_products,
            out_of_stock_count=out_of_stock_count,
            low_stock_count=low_stock_count,
        )

    def get_review_analytics(self) -> ReviewAnalytics:
        """Calculate review analytics including approval status"""
        total_reviews = self.db.query(func.count(Review.id)).scalar() or 0
        pending_reviews = (
            self.db.query(func.count(Review.id))
            .filter(Review.is_approved == False)
            .scalar()
            or 0
        )
        approved_reviews = (
            self.db.query(func.count(Review.id))
            .filter(Review.is_approved == True)
            .scalar()
            or 0
        )
        average_rating = self.db.query(func.avg(Review.rating)).scalar()

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
        query = self.db.query(User)

        # Apply filters
        if search:
            search_filter = or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
            query = query.filter(search_filter)

        if role:
            query = query.filter(User.role == role)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        users = query.offset(offset).limit(page_size).all()

        # Build user list with additional stats
        user_items = []
        for user in users:
            # Calculate total orders and spent
            total_orders = (
                self.db.query(func.count(Order.id))
                .filter(Order.user_id == user.id)
                .scalar()
                or 0
            )
            total_spent = (
                self.db.query(func.sum(Order.total_amount))
                .filter(Order.user_id == user.id)
                .scalar()
                or 0.0
            )

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

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.role = new_role
        self.db.commit()
        self.db.refresh(user)
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
        query = self.db.query(Order).join(User, Order.user_id == User.id)

        # Apply filters
        if status:
            query = query.filter(Order.status == status)
        if user_id:
            query = query.filter(Order.user_id == user_id)

        # Get total count
        total = query.count()

        # Apply pagination and ordering (newest first)
        offset = (page - 1) * page_size
        orders = (
            query.order_by(Order.order_date.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        # Build order list with user email
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

        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        order.status = new_status
        self.db.commit()
        self.db.refresh(order)
        return order

    def mark_order_shipped(
        self, order_id: int, shipped_at: Optional[datetime] = None
    ) -> Order:
        """Mark an order as shipped"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
            )

        order.status = "shipped"
        order.shipped_at = shipped_at or datetime.now()
        self.db.commit()
        self.db.refresh(order)
        return order

    # Review Moderation Methods
    def get_pending_reviews(
        self, page: int = 1, page_size: int = 20
    ) -> ReviewModerationResponse:
        """Get paginated list of pending reviews"""
        query = (
            self.db.query(Review)
            .join(User, Review.user_id == User.id)
            .join(Product, Review.product_id == Product.id)
            .filter(Review.is_approved == False)
        )

        total = query.count()

        offset = (page - 1) * page_size
        reviews = (
            query.order_by(Review.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

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
        query = (
            self.db.query(Review)
            .join(User, Review.user_id == User.id)
            .join(Product, Review.product_id == Product.id)
        )

        total = query.count()

        offset = (page - 1) * page_size
        reviews = (
            query.order_by(Review.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

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
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )

        review.is_approved = True
        self.db.commit()
        self.db.refresh(review)
        return review

    def reject_review(self, review_id: int) -> None:
        """Reject/delete a review"""
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )

        self.db.delete(review)
        self.db.commit()

    # Inventory Management Methods
    def get_low_stock_products(self, threshold: int = 10) -> List[InventoryAlert]:
        """Get products with low stock"""
        products = (
            self.db.query(Product)
            .filter(
                and_(Product.stock_quantity > 0, Product.stock_quantity < threshold)
            )
            .order_by(Product.stock_quantity.asc())
            .all()
        )

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
        updated_count = 0
        failed_products = []

        for update in updates:
            product = (
                self.db.query(Product).filter(Product.id == update.product_id).first()
            )
            if not product:
                failed_products.append(update.product_id)
                continue

            product.stock_quantity = update.stock_quantity
            updated_count += 1

        self.db.commit()

        return BulkInventoryUpdateResponse(
            updated_count=updated_count, failed_products=failed_products
        )
