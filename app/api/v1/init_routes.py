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
    app.include_router(router=audit.router, prefix="/audit")
    app.include_router(router=tax_rate.router, prefix="/tax-rates")
    app.include_router(router=shipping.router)
    app.include_router(router=shipping.admin_router)
