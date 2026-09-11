from fastapi import FastAPI

from app.api.v1.routes import (
    admin,
    brand,
    cart,
    category,
    elastic,
    healthcheck,
    order,
    payment,
    product,
    review,
    user,
    wishlist,
    coupon,
    audit,
    tax_rate,
    shipping,
    promotion,
)


def init_routes(app: FastAPI):
    app.include_router(router=healthcheck.router, prefix="/healthcheck")
    app.include_router(router=user.router, prefix="/users")
    app.include_router(router=category.router, prefix="/category")
    app.include_router(router=product.router, prefix="/product")
    app.include_router(router=brand.router, prefix="/brands")
    app.include_router(router=cart.router, prefix="/cart")
    app.include_router(router=order.router, prefix="/order")
    app.include_router(router=review.router, prefix="/reviews")
    app.include_router(router=payment.router, prefix="/payments")
    app.include_router(router=admin.router, prefix="/admin")
    app.include_router(router=wishlist.router, prefix="/wishlist")
    app.include_router(router=elastic.router, prefix="/elastic")
    app.include_router(router=coupon.router, prefix="/coupons")
    app.include_router(router=promotion.router, prefix="/promotions")
    app.include_router(router=audit.router, prefix="/audit")
    # No prefix here: tax_rate.router already declares
    # prefix="/admin/tax-rates" on itself (same pattern as
    # shipping.admin_router below) — adding one here doubled up to
    # /tax-rates/admin/tax-rates/... for every route in that file.
    app.include_router(router=tax_rate.router)
    app.include_router(router=shipping.router)
    app.include_router(router=shipping.admin_router)
