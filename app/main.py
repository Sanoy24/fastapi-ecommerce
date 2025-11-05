from fastapi import FastAPI
from app.api.v1.routes import healthcheck, user


app = FastAPI(root_path="/api/v1")
app.include_router(router=healthcheck.router, prefix="/healthcheck")
app.include_router(router=user.router, prefix="/users")
