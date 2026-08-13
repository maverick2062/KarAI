from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.notifications import send_email
from app.routers.deps import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    limiter,
    oauth2_scheme,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()

LOCKOUT_THRESHOLD = settings.account_lockout_threshold
LOCKOUT_DURATION_MINUTES = 30


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    generic_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if user is None:
        raise generic_error

    now = datetime.now(timezone.utc)
    if user.locked_until is not None and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()} after too many failed attempts",
        )

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
            user.locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            send_email(
                user.email,
                "KarAI: account locked",
                f"Your account was locked for {LOCKOUT_DURATION_MINUTES} minutes after "
                f"{LOCKOUT_THRESHOLD} failed login attempts. If this wasn't you, "
                "consider changing your password once unlocked.",
            )
        db.commit()
        raise generic_error

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    token = create_access_token(subject=user.id, role=user.role.value)
    return TokenResponse(access_token=token, expires_in_hours=settings.jwt_expiry_hours)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        return

    payload = decode_access_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        if db.get(RevokedToken, jti) is None:
            db.add(RevokedToken(jti=jti, expires_at=expires_at))
            db.commit()


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
