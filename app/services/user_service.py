from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate


def get_or_create_user(
    db: Session,
    user_data: UserCreate,
) -> tuple[User, bool]:
    """
    Find a user by platform_user_id.

    Returns:
        (user, created)
        - created is True when a new user was created.
        - created is False when the user already existed.
    """
    user = db.scalar(
        select(User).where(User.platform_user_id == user_data.platform_user_id)
    )

    if user is not None:
        # Only fill in the name if the existing user has no name yet.
        if user.name is None and user_data.name is not None:
            user.name = user_data.name
            db.commit()
            db.refresh(user)

        return user, False

    user = User(
        platform_user_id=user_data.platform_user_id,
        name=user_data.name,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
        return user, True

    except IntegrityError:
        # Another request may have created this user at almost the same time.
        db.rollback()

        existing_user = db.scalar(
            select(User).where(User.platform_user_id == user_data.platform_user_id)
        )

        if existing_user is None:
            raise

        return existing_user, False