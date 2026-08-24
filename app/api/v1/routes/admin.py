from fastapi import APIRouter, Depends, Query, status
from typing import Annotated, Optional
from datetime import datetime

from app.dependencies import require_admin, get_db
from app.services.admin_service import AdminService
from app.schema.admin_schema import (
    DashboardOverview,
    SalesAnalytics,
    UserAnalytics,
    ProductAnalytics,
    ReviewAnalytics,
    UserManagementResponse,
    UpdateUserRoleRequest,
    OrderListItem,
    OrderManagementResponse,
    OrderUpdateStatus,
    OrderUpdateShipping,
    ReviewModerationResponse,
    ReviewModerationItem,
    InventoryAlert,
    BulkInventoryUpdateRequest,
    BulkInventoryUpdateResponse,
    SalesOverTime,
    TopSellingProduct,
)
from app.schema.user_schema import UserPublic
from app.services.email_service import send_order_shipped_email
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks, HTTPException

router = APIRouter(tags=["Admin"])


def get_admin_service(db: Annotated[Session, Depends(get_db)]) -> AdminService:
    """Dependency to get admin service"""
    return AdminService(db=db)


# Analytics Endpoints
@router.get(
    "/dashboard",
    response_model=DashboardOverview,
    summary="Get complete dashboard overview",
    description="Get comprehensive analytics including sales, users, products, and reviews",
)
async def get_dashboard(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Get high-level dashboard analytics"""
    return admin_service.get_dashboard_overview()


@router.get(
    "/analytics/sales",
    summary="Get sales analytics",
)
def get_sales_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Get sales analytics"""
    return admin_service.get_sales_analytics()


@router.get(
    "/analytics/sales/trends",
    response_model=list[SalesOverTime],
    summary="Get sales trends over time",
)
def get_sales_trends(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """Get sales revenue and order counts over time (Admin only)."""
    from sqlalchemy import select, func
    from app.models.order import Order
    from datetime import datetime, timedelta
    
    db = admin_service.db
    cutoff = datetime.now() - timedelta(days=days)
    
    # SQLite friendly date truncation
    stmt = (
        select(
            func.strftime('%Y-%m-%d', Order.order_date).label('date'),
            func.sum(Order.total_amount).label('revenue'),
            func.count(Order.id).label('orders_count')
        )
        .where(Order.order_date >= cutoff)
        .where(Order.status != 'cancelled')
        .group_by(func.strftime('%Y-%m-%d', Order.order_date))
        .order_by('date')
    )
    
    results = db.execute(stmt).all()
    return [{"date": r.date, "revenue": r.revenue or 0.0, "orders_count": r.orders_count} for r in results]


@router.get(
    "/analytics/top-products",
    response_model=list[TopSellingProduct],
    summary="Top selling products",
)
def get_top_products(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    limit: int = Query(10, ge=1, le=50),
):
    """Get the most sold products (Admin only)."""
    from sqlalchemy import select, func
    from app.models.order_item import OrderItem
    from app.models.product import Product
    from app.models.order import Order
    
    db = admin_service.db
    stmt = (
        select(
            Product.id.label('product_id'),
            Product.name.label('product_name'),
            func.sum(OrderItem.quantity).label('total_quantity_sold'),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label('total_revenue')
        )
        .join(OrderItem, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status != 'cancelled')
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )
    
    results = db.execute(stmt).all()
    return [{
        "product_id": r.product_id,
        "product_name": r.product_name,
        "total_quantity_sold": r.total_quantity_sold or 0,
        "total_revenue": r.total_revenue or 0.0
    } for r in results]


@router.get(
    "/analytics/users",
    response_model=UserAnalytics,
    summary="Get user analytics",
    description="Get user analytics including total users and growth metrics",
)
async def get_user_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Get user analytics"""
    return admin_service.get_user_analytics()


@router.get(
    "/analytics/products",
    response_model=ProductAnalytics,
    summary="Get product analytics",
    description="Get product analytics including inventory status",
)
async def get_product_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Get product analytics"""
    return admin_service.get_product_analytics()


@router.get(
    "/analytics/reviews",
    response_model=ReviewAnalytics,
    summary="Get review analytics",
    description="Get review analytics including approval status and average rating",
)
async def get_review_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Get review analytics"""
    return admin_service.get_review_analytics()


# User Management Endpoints
@router.get(
    "/users",
    response_model=UserManagementResponse,
    summary="List all users",
    description="Get paginated list of all users with optional search and role filters",
)
async def list_all_users(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    role: Optional[str] = Query(
        None, description="Filter by role: 'customer' or 'admin'"
    ),
):
    """List all users with pagination and filters"""
    return admin_service.get_all_users(
        page=page, page_size=page_size, search=search, role=role
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=UserPublic,
    summary="Update user role",
    description="Change a user's role between 'customer' and 'admin'",
)
async def update_user_role(
    user_id: int,
    role_update: UpdateUserRoleRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Update a user's role"""
    user = admin_service.update_user_role(user_id=user_id, new_role=role_update.role)
    return UserPublic.model_validate(user)


# Order Management Endpoints
@router.get(
    "/orders",
    response_model=OrderManagementResponse,
    summary="List all orders",
    description="Get paginated list of all orders with optional filters",
)
async def list_all_orders(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(
        None,
        description="Filter by status: 'pending', 'paid', 'shipped', 'delivered', 'cancelled'",
    ),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
):
    """List all orders with pagination and filters"""
    return admin_service.get_all_orders(
        page=page, page_size=page_size, status=status, user_id=user_id
    )


@router.put("/orders/{order_id}/status", response_model=OrderListItem)
def update_order_status(
    order_id: int,
    payload: OrderUpdateStatus,
    admin_user: Annotated[UserPublic, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
):
    """Update order status (Admin)"""
    from app.models.order import Order
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.status = payload.status
    db.commit()
    db.refresh(order)
    
    return OrderListItem(
        id=order.id,
        order_number=order.order_number,
        user_id=order.user_id,
        user_email=order.user.email,
        total_amount=order.total_amount,
        status=order.status,
        payment_status=order.payment_status,
        order_date=order.order_date,
        shipped_at=order.shipped_at,
    )


@router.put("/orders/{order_id}/shipping", response_model=OrderListItem)
def update_order_shipping(
    order_id: int,
    payload: OrderUpdateShipping,
    admin_user: Annotated[UserPublic, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Update order shipping details (Admin)"""
    from app.models.order import Order
    from datetime import datetime
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.tracking_number = payload.tracking_number
    order.shipping_carrier = payload.shipping_carrier
    
    if order.status != "shipped" and order.status != "delivered":
        order.status = "shipped"
        order.shipped_at = datetime.now()
        
        # Dispatch shipped email asynchronously
        background_tasks.add_task(
            send_order_shipped_email,
            to_address=order.user.email,
            order_number=order.order_number,
            tracking_number=order.tracking_number,
            carrier=order.shipping_carrier,
        )
        
    db.commit()
    db.refresh(order)
    
    return OrderListItem(
        id=order.id,
        order_number=order.order_number,
        user_id=order.user_id,
        user_email=order.user.email,
        total_amount=order.total_amount,
        status=order.status,
        payment_status=order.payment_status,
        order_date=order.order_date,
        shipped_at=order.shipped_at,
    )


# --- REVIEWS ---
@router.get(
    "/reviews/pending",
    response_model=ReviewModerationResponse,
    summary="Get pending reviews",
)
async def get_pending_reviews(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get pending reviews for moderation"""
    return admin_service.get_pending_reviews(page=page, page_size=page_size)


@router.get(
    "/reviews",
    response_model=ReviewModerationResponse,
    summary="Get all reviews",
)
async def get_all_reviews(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get all reviews"""
    return admin_service.get_all_reviews(page=page, page_size=page_size)


@router.post(
    "/reviews/{review_id}/approve",
    summary="Approve review",
    description="Approve a pending review",
)
async def approve_review(
    review_id: int,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Approve a review"""
    review = admin_service.approve_review(review_id=review_id)
    return {"message": "Review approved successfully", "review_id": review.id}


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reject/delete review",
    description="Reject and delete a review",
)
async def reject_review(
    review_id: int,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Reject/delete a review"""
    admin_service.reject_review(review_id=review_id)
    return None


# Inventory Management Endpoints
@router.get(
    "/inventory/low-stock",
    response_model=list[InventoryAlert],
    summary="Get low stock alerts",
    description="Get products with stock below threshold",
)
async def get_low_stock_alerts(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    threshold: int = Query(10, ge=1, description="Stock threshold for alerts"),
):
    """Get low stock product alerts"""
    return admin_service.get_low_stock_products(threshold=threshold)


@router.patch(
    "/inventory/bulk-update",
    response_model=BulkInventoryUpdateResponse,
    summary="Bulk update inventory",
    description="Update stock quantities for multiple products",
)
async def bulk_update_inventory(
    update_request: BulkInventoryUpdateRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Bulk update product inventory"""
    return admin_service.bulk_update_inventory(updates=update_request.updates)
