from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserUpdateRequest
from app.workers.celery_tasks import recompute_for_user_change

router = APIRouter(prefix="/users", tags=["users"])

# Attributes that, if changed, can affect task eligibility and must trigger a recompute.
ELIGIBILITY_FIELDS = {"department", "experience_years", "location", "is_active"}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Story 3: updating a user's profile can change which tasks they're eligible for. Any
    change to an eligibility-relevant field enqueues a bounded recompute after commit."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    update_data = payload.model_dump(exclude_unset=True)
    eligibility_changed = any(field in update_data and field in ELIGIBILITY_FIELDS for field in update_data)

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    if eligibility_changed:
        recompute_for_user_change.delay(user.id)

    return user
