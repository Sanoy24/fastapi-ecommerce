from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from typing import Annotated, Optional
from datetime import datetime

from app.dependencies import require_admin, get_db
from app.services.admin_service import AdminService
from app.schema.admin_schema import (
    DashboardOverview,
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
    InventoryAlert,
    BulkInventoryUpdateRequest,
    BulkInventoryUpdateResponse,
    ProductImportResponse,
    SalesOverTime,
    TopSellingProduct,
)
from app.schema.user_schema import UserPublic
from app.schema.return_schema import ReturnResponse, ReturnResolutionRequest
from app.services.email_service import send_order_shipped_email
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks, HTTPException
from app.services.back_in_stock_service import notify_back_in_stock_subscribers

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


def build_sales_trends_stmt(cutoff: datetime):
    """
    Build the daily sales-trend aggregate, grouped by calendar day.

    Day truncation is spelled `func.date()` because that is the one form
    PostgreSQL and SQLite agree on: PostgreSQL parses it as the function-call
    syntax for `CAST(x AS date)`, SQLite as its own built-in `date()`. The
    alternatives all break on one side or the other —
    `strftime()` does not exist in PostgreSQL (which is how this endpoint used
    to 500 in production), `date_trunc()` does not exist in SQLite, and
    `CAST(x AS DATE)` silently evaluates to just the year on SQLite.

    Exposed at module level so the statement can be compiled against a
    PostgreSQL dialect in tests without needing a live database.
    """
    from sqlalchemy import select, func
    from app.models.order import Order

    day = func.date(Order.order_date)
    return (
        select(
            day.label("date"),
            func.sum(Order.total_amount).label("revenue"),
            func.count(Order.id).label("orders_count"),
        )
        .where(Order.order_date >= cutoff)
        .where(Order.status != "cancelled")
        .group_by(day)
        .order_by(day)
    )


@router.get(
    "/analytics/sales/trends",
    response_model=list[SalesOverTime],
    summary="Get sales trends over time",
)
def get_sales_trends(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    days: int = Query(30, ge=1, le=365,
                      description="Number of days to analyze"),
):
    """Get sales revenue and order counts over time (Admin only)."""
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=days)
    results = admin_service.db.execute(build_sales_trends_stmt(cutoff)).all()

    return [
        {
            # PostgreSQL hands back a date object here, SQLite a 'YYYY-MM-DD'
            # string; the response schema wants the string form either way.
            "date": r.date.isoformat() if hasattr(r.date, "isoformat") else str(r.date),
            "revenue": float(r.revenue or 0.0),
            "orders_count": r.orders_count,
        }
        for r in results
    ]


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
            func.sum(OrderItem.quantity *
                     OrderItem.unit_price).label('total_revenue')
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
    user = admin_service.update_user_role(
        user_id=user_id, new_role=role_update.role, admin_id=current_admin.id)
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


def _order_contact_email(order) -> str:
    """The account email, or the guest email for a guest order.

    ck_orders_user_or_guest_email guarantees one of these is always set —
    the assert documents that invariant for mypy rather than leaving the
    fallback typed as str | None.
    """
    email = order.user.email if order.user else order.guest_email
    assert email, f"order {order.id} has neither a user nor a guest_email"
    return email


def _order_list_item(order) -> "OrderListItem":
    """Build the admin OrderListItem response, correctly for a guest order
    too — order.user is None for one, so order.user.email would raise.
    """
    return OrderListItem(
        id=order.id,
        order_number=order.order_number,
        user_id=order.user_id,
        user_email=_order_contact_email(order),
        is_guest_order=order.user_id is None,
        total_amount=order.total_amount,
        status=order.status,
        payment_status=order.payment_status,
        order_date=order.order_date,
        shipped_at=order.shipped_at,
    )


@router.put("/orders/{order_id}/status", response_model=OrderListItem)
def update_order_status(
    order_id: int,
    payload: OrderUpdateStatus,
    admin_user: Annotated[UserPublic, Depends(require_admin)],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
):
    """Update order status (Admin)"""
    order = admin_service.update_order_status(
        order_id, payload.status, admin_user.id)
    return _order_list_item(order)


@router.put("/orders/{order_id}/shipping", response_model=OrderListItem)
def update_order_shipping(
    order_id: int,
    payload: OrderUpdateShipping,
    admin_user: Annotated[UserPublic, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
):
    """Update order shipping details and create shipment (Admin)"""
    admin_service = AdminService(db)
    order = admin_service.mark_order_shipped(
        order_id=order_id,
        admin_id=admin_user.id,
        tracking_number=payload.tracking_number,
        carrier=payload.shipping_carrier
    )

    # Dispatch shipped email asynchronously — to the account email, or the
    # guest's email for a guest order.
    background_tasks.add_task(
        send_order_shipped_email,
        to_address=_order_contact_email(order),
        order_number=order.order_number,
        tracking_number=payload.tracking_number,
        carrier=payload.shipping_carrier,
    )

    return _order_list_item(order)


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


class RefundRequest(BaseModel):
    amount: float
    reason: str


@router.post("/orders/{order_id}/refund", summary="Refund an order")
def refund_order(
    order_id: int,
    request: RefundRequest,
    db: Session = Depends(get_db),
    admin: UserPublic = Depends(require_admin)
):
    """Admin endpoint to refund a payment for an order."""
    from app.services.payment_service import PaymentService
    payment_service = PaymentService(db)
    return payment_service.refund_payment(
        order_id=order_id,
        admin_id=admin.id,
        amount=request.amount,
        reason=request.reason,
    )


@router.get("/returns", response_model=list[ReturnResponse], summary="List all return requests")
def list_return_requests(
    db: Session = Depends(get_db),
    admin: UserPublic = Depends(require_admin),
    status: Optional[str] = None
):
    """Admin endpoint to list return requests."""
    from app.models.return_request import ReturnRequest
    from sqlalchemy import select

    stmt = select(ReturnRequest)
    if status:
        stmt = stmt.where(ReturnRequest.status == status)

    returns = db.scalars(stmt).all()
    return returns


@router.patch("/returns/{return_id}", response_model=ReturnResponse, summary="Approve or reject a return")
def resolve_return(
    return_id: int,
    request: ReturnResolutionRequest,
    db: Session = Depends(get_db),
    admin: UserPublic = Depends(require_admin)
):
    """
    Admin endpoint to resolve a return request.

    Approving a return restocks the returned quantities and automatically
    refunds the corresponding amount — previously this only flipped the
    return's own status and the order's status, leaving an admin to
    remember to restock and issue the refund as two separate manual steps.
    """
    from app.models.return_request import ReturnRequest
    from app.models.order_item import OrderItem
    from app.models.inventory_transaction import InventoryTransaction
    from app.crud.order import OrderCrud
    from app.services.payment_service import PaymentService
    from sqlalchemy import func, select

    return_req = db.get(ReturnRequest, return_id)
    if not return_req:
        raise HTTPException(status_code=404, detail="Return request not found")

    if return_req.status != "pending":
        raise HTTPException(
            status_code=400, detail=f"Return already {return_req.status}")

    if request.status not in ["approved", "rejected"]:
        raise HTTPException(
            status_code=400, detail="Status must be approved or rejected")

    order_crud = OrderCrud(db)
    refund_amount = 0.0

    if request.status == "approved":
        # A second, separate return request could target the same order
        # item as one already approved — without this check, approving it
        # would restock and refund that item a second time.
        other_approved_items = {
            item["order_item_id"]
            for other in db.scalars(
                select(ReturnRequest).where(
                    ReturnRequest.order_id == return_req.order_id,
                    ReturnRequest.status == "approved",
                    ReturnRequest.id != return_req.id,
                )
            ).all()
            for item in other.items
        }
        overlap = {i["order_item_id"]
                   for i in return_req.items} & other_approved_items
        if overlap:
            raise HTTPException(
                status_code=400,
                detail=f"Item(s) {sorted(overlap)} were already covered by a previously approved return",
            )

        for returned in return_req.items:
            order_item = db.get(OrderItem, returned["order_item_id"])
            if not order_item:
                continue  # validated to exist at request time; tolerate a since-deleted row
            if returned["quantity"] > order_item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot return {returned['quantity']} of item {order_item.id} — only {order_item.quantity} were ordered",
                )

            refund_amount += float(order_item.unit_price) * \
                returned["quantity"]

            # A variant item restocks the variant's own pool, not the
            # parent product's — they're separate (see
            # ProductVariant.available_stock).
            target = order_item.variant if (
                order_item.variant_id and order_item.variant) else order_item.product
            qty_before = target.stock_quantity
            target.stock_quantity += returned["quantity"]

            db.add(InventoryTransaction(
                product_id=order_item.product_id,
                variant_id=order_item.variant_id,
                order_id=return_req.order_id,
                transaction_type="return",
                quantity_change=returned["quantity"],
                quantity_before=qty_before,
                quantity_after=target.stock_quantity,
                note=f"Restocked from approved return #{return_req.id}",
                created_by=admin.id,
            ))

            notify_back_in_stock_subscribers(
                db,
                product_id=order_item.product_id,
                variant_id=order_item.variant_id,
                old_quantity=qty_before,
                new_quantity=target.stock_quantity,
            )

    return_req.status = request.status
    return_req.resolution_note = request.resolution_note
    return_req.resolved_at = func.current_timestamp()

    new_order_status = "return_approved" if request.status == "approved" else "delivered"
    try:
        order_crud.update_order_status(
            return_req.order_id, new_order_status, admin_id=admin.id)
    except HTTPException:
        # Ignore transition errors if the order is already in that state
        pass

    refund_error = None
    if request.status == "approved" and refund_amount > 0:
        try:
            PaymentService(db).refund_payment(
                order_id=return_req.order_id,
                admin_id=admin.id,
                amount=refund_amount,
                reason="return_approved",
            )
        except HTTPException as e:
            # Restocking and the return's own approval still stand — an
            # automatic refund failing (e.g. no completed payment on file,
            # a Stripe error) shouldn't also leave the returned stock
            # un-restocked. The admin follows up manually via
            # POST /admin/orders/{order_id}/refund; refund_error below
            # surfaces that this order still needs it.
            refund_error = str(e.detail)

    db.commit()
    db.refresh(return_req)

    response = ReturnResponse.model_validate(return_req)
    response.refund_error = refund_error
    return response


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
    review = admin_service.approve_review(
        review_id=review_id, admin_id=current_admin.id)
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
    admin_service.reject_review(review_id=review_id, admin_id=current_admin.id)
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
    return admin_service.bulk_update_inventory(updates=update_request.updates, admin_id=current_admin.id)


@router.get(
    "/products/export",
    summary="Export the product catalog as CSV",
    description="Every product regardless of status, in the same column set /products/import reads back.",
)
async def export_products(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
):
    csv_content = admin_service.export_products_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="products.csv"'},
    )


@router.post(
    "/products/import",
    response_model=ProductImportResponse,
    summary="Bulk create/update products from a CSV file",
    description=(
        "A row with an id column updates that product; a row without one creates a new one "
        "(name and price required). One bad row is reported in failed_rows rather than "
        "aborting the rest of the import."
    ),
)
async def import_products(
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    current_admin: Annotated[UserPublic, Depends(require_admin)],
    file: UploadFile = File(..., description="CSV file — see GET /admin/products/export for the column set"),
):
    content = (await file.read()).decode("utf-8-sig")
    return admin_service.import_products_csv(content, admin_id=current_admin.id)
