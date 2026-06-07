from fastapi import (APIRouter, Depends, status) 
from sqlalchemy.orm import Session
from app.database.session import get_db 
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import (UserRegister, UserLogin, TokenResponse, UserResponse)
from app.services.auth_service import (register_user, login_user)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    return register_user(
        user_data=user_data,
        db=db 
    )

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK
)
def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    return login_user(
        user_data=user_data,
        db=db 
    )

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK
)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    return current_user