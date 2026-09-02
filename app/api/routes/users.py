from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

from app.schemas.user import UserCreate, UserGetOrCreateResponse, UserRead
from app.services.user_service import get_or_create_user

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    existing_user = db.scalar(
        select(User).where(User.platform_user_id == user_data.platform_user_id)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this platform_user_id already exists.",
        )

    user = User(
        platform_user_id=user_data.platform_user_id,
        name=user_data.name,
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this platform_user_id already exists.",
        )

    db.refresh(user)
    return user

@router.post(
    "/get-or-create",
    response_model=UserGetOrCreateResponse,
)
def get_or_create_user_endpoint(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> UserGetOrCreateResponse:
    user, created = get_or_create_user(
        db=db,
        user_data=user_data,
    )

    return UserGetOrCreateResponse(
        created=created,
        user=UserRead.model_validate(user),
    )

@router.get(
    "/{platform_user_id}",
    response_model=UserRead,
)
def get_user(
    platform_user_id: str,
    db: Session = Depends(get_db),
) -> User:
    user = db.scalar(
        select(User).where(User.platform_user_id == platform_user_id)
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return user