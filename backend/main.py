from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.logging import configure_logging
from routers.admin import router as admin_router
from routers.ai import router as ai_router
from routers.auth import router as auth_router
from routers.businesses import router as businesses_router
from routers.coupons import router as coupons_router
from routers.expansion import router as expansion_router
from routers.manager import router as manager_router
from routers.me import router as me_router
from routers.performance import router as performance_router
from routers.pilot import router as pilot_router
from routers.recommendations import router as recommendations_router
from routers.referral import router as referral_router
from routers.reservations import router as reservations_router
from routers.transactions import router as transactions_router

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
app.include_router(expansion_router)
app.include_router(manager_router)
app.include_router(performance_router)
app.include_router(ai_router)
app.include_router(recommendations_router)
app.include_router(reservations_router)
app.include_router(admin_router)
app.include_router(transactions_router)
app.include_router(referral_router)
app.include_router(me_router)
app.include_router(pilot_router)


def _strip_unencodable(value: object) -> object:
    """value 안의 문자열 중 UTF-8로 다시 인코딩할 수 없는 것(예: lone
    surrogate)을 재귀적으로 안전한 표시값으로 바꾼다. 이미 jsonable_encoder를
    거친 값(str/int/float/bool/None/dict/list만 남음)에 대해서만 쓴다."""
    if isinstance(value, str):
        try:
            value.encode("utf-8")
            return value
        except UnicodeEncodeError:
            return "<표시할 수 없는 값>"
    if isinstance(value, dict):
        return {k: _strip_unencodable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_unencodable(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def safe_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """PILOT AUDIT TASK 1에서 발견 - lone surrogate처럼 UTF-8로 다시 인코딩할
    수 없는 값이 들어오면 core/text_validation.py가 이를 올바르게 422로
    거부하지만, FastAPI 기본 핸들러가 그 값을 에러 응답의 "input"에 그대로
    되돌려주려다 JSON 직렬화 자체가 실패해서 422 대신 처리되지 않은 500으로
    죽는다. jsonable_encoder로 우선 FastAPI 기본 동작과 동일하게 안전한
    타입으로 바꾼 뒤, 그 안에 남은 인코딩 불가 문자열만 추가로 치환한다."""
    safe_detail = _strip_unencodable(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": safe_detail})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
