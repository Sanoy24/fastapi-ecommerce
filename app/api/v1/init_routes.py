from fastapi import FastAPI

from app.api.v1.routes import (
    admin,
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
)


def init_routes(app: FastAPI):
    app.include_router(router=healthcheck.router, prefix="/healthcheck")
    app.include_router(router=user.router, prefix="/users")
    app.include_router(router=category.router, prefix="/category")
    app.include_router(router=product.router, prefix="/product")
    app.include_router(router=cart.router, prefix="/cart")
    app.include_router(router=order.router, prefix="/order")
    app.include_router(router=review.router, prefix="/reviews")
    app.include_router(router=payment.router, prefix="/payments")
    app.include_router(router=admin.router, prefix="/admin")
    app.include_router(router=wishlist.router, prefix="/wishlist")
    app.include_router(router=elastic.router, prefix="/elastic")
