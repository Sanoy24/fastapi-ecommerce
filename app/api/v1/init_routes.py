from fastapi import FastAPI

from app.api.v1.routes import cart, category, healthcheck, product, user, order


def init_routes(app: FastAPI):
    app.include_router(router=healthcheck.router, prefix="/healthcheck")
    app.include_router(router=user.router, prefix="/users")
    app.include_router(router=category.router, prefix="/category")
    app.include_router(router=product.router, prefix="/product")
    app.include_router(router=cart.router, prefix="/cart")
    app.include_router(router=order.router, prefix="/order")
