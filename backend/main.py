from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import configure_logging
from routers.ai import router as ai_router
from routers.auth import router as auth_router
from routers.businesses import router as businesses_router
from routers.coupons import router as coupons_router
from routers.recommendations import router as recommendations_router

configure_logging()

app = FastAPI(title="YEONGJONG AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(businesses_router)
app.include_router(coupons_router)
app.include_router(ai_router)
app.include_router(recommendations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
