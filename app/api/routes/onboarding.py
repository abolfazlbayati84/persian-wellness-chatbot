from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.profile_service import (
    create_or_replace_profile,
    get_profile_by_user_id,
    patch_profile,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/profile", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_or_replace_profile_endpoint(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
) -> ProfileRead:
    try:
        profile = create_or_replace_profile(db=db, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ProfileRead.model_validate(profile)


@router.get("/profile/{user_id}", response_model=ProfileRead)
def get_profile_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
) -> ProfileRead:
    try:
        profile = get_profile_by_user_id(db=db, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ProfileRead.model_validate(profile)


@router.patch("/profile/{user_id}", response_model=ProfileRead)
def patch_profile_endpoint(
    user_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
) -> ProfileRead:
    try:
        profile = patch_profile(db=db, user_id=user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ProfileRead.model_validate(profile)