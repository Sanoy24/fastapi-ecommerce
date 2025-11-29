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
    OrderManagementResponse,
    UpdateOrderStatusRequest,
    MarkOrderShippedRequest,
    ReviewModerationResponse,
    InventoryAlert,
    BulkInventoryUpdateRequest,
    BulkInventoryUpdateResponse,
)
from app.schema.user_schema import UserPublic
from sqlalchemy.orm import Session

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
    """Get complete admin dashboard overview with all analytics"""
    return admin_service.get_dashboard_overview()


@router.get(
    "/analytics/sales",
    response_model=SalesAnalytics,
    summary="Get sales analytics",
    description="Get detailed sales analytics including revenue and order statistics",
)
async def get_sales_analytics(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Get sales analytics"""
    return admin_service.get_sales_analytics()


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


@router.patch(
    "/orders/{order_id}/status",
    summary="Update order status",
    description="Update an order's status",
)
async def update_order_status(
    order_id: int,
    status_update: UpdateOrderStatusRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Update an order's status"""
    order = admin_service.update_order_status(
        order_id=order_id, new_status=status_update.status
    )
    return {
        "message": "Order status updated successfully",
        "order_id": order.id,
        "new_status": order.status,
    }


@router.patch(
    "/orders/{order_id}/shipping",
    summary="Mark order as shipped",
    description="Mark an order as shipped and set shipping timestamp",
)
async def mark_order_shipped(
    order_id: int,
    shipping_data: MarkOrderShippedRequest,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    """Mark an order as shipped"""
    order = admin_service.mark_order_shipped(
        order_id=order_id, shipped_at=shipping_data.shipped_at
    )
    return {
        "message": "Order marked as shipped",
        "order_id": order.id,
        "shipped_at": order.shipped_at,
    }


# Review Moderation Endpoints
@router.get(
    "/reviews/pending",
    response_model=ReviewModerationResponse,
    summary="Get pending reviews",
    description="Get paginated list of reviews awaiting approval",
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
    description="Get paginated list of all reviews",
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
