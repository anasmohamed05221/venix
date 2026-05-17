from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from utils.deps import db_dependency
from starlette import status
from schemas.auth import (Token, VerifyEmailRequest, CreateUserRequest, ForgotPasswordRequest,
                          RevokeTokenRequest, RefreshTokenRequest, ResetPasswordRequest, ResendVerificationRequest)
from services.auth import AuthService
from services.token import TokenService
from middleware.rate_limiter import limiter
from utils.logger import get_logger

# Setup logger
logger = get_logger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def create_user(request: Request, body: CreateUserRequest, db: db_dependency):
    """Register a new user and send verification email."""
    user = await AuthService.create_user(body, db)

    logger.info(
        "User registered successfully",
        extra={"user_id": user.id, "email": user.email}
    )

    return {"message": "Registration successful. A verification email will be sent to your inbox shortly. If you don't receive it, you can request a new one."}


@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, db: db_dependency, form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user and return access + refresh token pair."""
    user = await AuthService.authenticate_user(form_data.username, form_data.password, db)

    token = await TokenService.create_tokens(user.email, user.id, user.role, db)

    # Log successful login
    logger.info(
        "User logged in successfully",
        extra={"user_id": user.id, "email": user.email}
    )

    return token



@router.post("/verify", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def verify_email(request: Request, body: VerifyEmailRequest, db: db_dependency):
    """
    Verifies user's email with the provided code.
    
    Checks:
    - User exists
    - Not already verified
    - Code matches
    - Code not expired
    """
    user = await AuthService.verify_user(body, db)

    # Log successful verification
    logger.info(
        "Email verified successfully",
        extra={"user_id": user.id, "email": body.email}
    )

    return {"message": "Email verified successfully"}



@router.post("/refresh", response_model=Token)
@limiter.limit("10/minute")
async def refresh_token(request: Request, body: RefreshTokenRequest, db: db_dependency):
    """
    Get new access token using refresh token.
    """
    token = await TokenService.refresh_access_token(body.refresh_token, db)

    # Log token refresh (extract user_id from token if available)
    logger.info("Access token refreshed")

    return token


@router.post("/logout", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def logout(request: Request, body: RevokeTokenRequest, db: db_dependency):
    """
    Revoke refresh token (logout).
    """
    await TokenService.revoke_token(body.refresh_token, db)

    logger.info("User logged out")

    return {"message": "Logged out successfully"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def resend_verification(request: Request, body: ResendVerificationRequest, db: db_dependency):
    """Resend verification email to an unverified account."""
    await AuthService.resend_verification(db, body.email)
    return {"message": "If your email is registered and unverified, a new verification code has been sent."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def forgot_password_request(request: Request, body: ForgotPasswordRequest, db: db_dependency):
    """Request password reset via email."""
    await AuthService.forgot_password(db, body.email)
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest, db: db_dependency):
    """Reset password using a valid reset token (public endpoint)."""
    await AuthService.reset_password(db, body.token, body.new_password)
    return {"message": "Password updated successfully. Please login again."}

