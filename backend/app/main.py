from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.routers import advance_tax as advance_tax_router
from app.routers import ais as ais_router
from app.routers import auth as auth_router
from app.routers import reports as reports_router
from app.routers import tds as tds_router
from app.routers import transactions as transactions_router
from app.routers import users as users_router
from app.security import limiter

settings = get_settings()

app = FastAPI(
    title="KarAI API",
    description=(
        "Consumer TDS event detection & advance-tax intelligence for Indian "
        "individual taxpayers and freelancers, under the Income Tax Act 2025. "
        "AI-assisted, advisory only — verify with a Chartered Accountant or the "
        "applicable CBDT notification before relying on any output for filing."
    ),
    version="0.1.0",
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again shortly."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Applies the Limiter's default_limits (100/min per authenticated user, see
# app.security.limiter) to every route automatically — NFR-09 requires this
# on all endpoints, not just the ones with an explicit @limiter.limit(...).
app.add_middleware(SlowAPIMiddleware)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(transactions_router.router)
app.include_router(tds_router.router)
app.include_router(advance_tax_router.router)
app.include_router(ais_router.router)
app.include_router(reports_router.router)
