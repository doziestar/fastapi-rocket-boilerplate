from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.auth.functions import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_refresh_token,
)

from .models import RevokedToken, User
from .responses import responses_content
from .schemas import RefreshToken, TokenRefreshed, Tokens, UserRegistration

router = APIRouter(prefix="/user", tags=["user"])


@router.post(
    "/register",
    responses={
        **responses_content["UserSuccessfullyRegistered"],
        **responses_content["UserAlreadyRegistered"],
    },
    status_code=status.HTTP_201_CREATED,
)
def register_user(user: UserRegistration, response: Response):
    """Register new user
    - Check if the user exists
    - Save in DB
    return: Confirmation OR denial
    """
    # Check if the user exists
    if User.get_one(key=User.username, value=user.username):
        raise HTTPException(
            status_code=400, detail="This user is already registered"
        )

    # Hash password
    hashed_password = hash_password(user.password)

    # Save the new user
    user = User(username=user.username, hashed_password=hashed_password).save()
    response.status_code = status.HTTP_201_CREATED
    return f"User '{user.username}' created"


@router.post(
    "/login",
    response_model=Tokens,
    responses={**responses_content["LoginInvalidCredentials"]},
)
def login_user(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login with username and password
    return: A pair of access and refresh tokens OR denial
    """
    # Authenticate user
    if not (
        tokens := User.authenticate_user(
            form_data.username, form_data.password
        )
    ):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # Return tokens
    return tokens


@router.post(
    "/refresh-token",
    response_model=TokenRefreshed,
    responses={**responses_content["TokenUnauthorizedOrRevoked"]},
)
def refresh_token(refresh_token: RefreshToken):
    """
    Refresh access token from a refresh token
    """
    refresh_token = refresh_token.refresh_token
    # Validate the refresh token and get the user
    if not (payload := verify_refresh_token(refresh_token)):
        raise HTTPException(status_code=400, detail="Not authorized")

    username = payload.get("sub")

    # Check if the refresh token is revoked
    if RevokedToken.is_revoked(refresh_token):
        raise HTTPException(status_code=400, detail="Revoked refresh token")

    # Return new access token
    access_token = create_access_token(username)
    return TokenRefreshed(access_token=access_token, token_type="bearer")


@router.post(
    "/logout",
    responses={**responses_content["TokenSuccessfullyRevoked"]},
)
def logout(refresh_token: RefreshToken):
    """
    Revoke refresh token
    # TODO: Once installed Celery,
    # TODO: include a cron task to remove expired revoked tokens
    return: Always return 200 OK (for security reasons)
    """
    refresh_token = refresh_token.refresh_token
    # Validate token
    if payload := verify_refresh_token(refresh_token):
        # Extract payload
        username = payload["sub"]
        expiration_date = payload["exp"]
        token = refresh_token

        # Save revoked token in DB
        RevokedToken(
            username=username, expiration_date=expiration_date, token=token
        ).save()

    return {"message": "Refresh token successfully revoked"}


@router.get(
    "/protected",
    responses={**responses_content["ProtectedRouteAccess"]},
)
def protected_route(current_user: str = Depends(get_current_user)):
    """Endpoint for auth test"""
    return {
        "message": (
            f"¡Hola, {current_user}! This is a protected url and you are"
            " inside!"
        )
    }
