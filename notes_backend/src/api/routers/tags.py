from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db import get_db
from src.api.models import Tag, note_tags
from src.api.schemas import TagCreate, TagOut

router = APIRouter(prefix="/tags", tags=["tags"])


class TagWithCount(TagOut):
    count: int = Field(..., description="Number of notes currently associated with this tag.")


@router.get(
    "",
    response_model=List[TagWithCount],
    summary="List tags",
    description="List all tags, optionally with a prefix filter, and include usage counts.",
)
# PUBLIC_INTERFACE
async def list_tags(
    db: AsyncSession = Depends(get_db),
    prefix: str | None = Query(None, description="Optional prefix filter on tag name."),
) -> List[TagWithCount]:
    """List tags with counts."""
    stmt = (
        select(
            Tag,
            func.count(note_tags.c.note_id).label("count"),
        )
        .outerjoin(note_tags, Tag.id == note_tags.c.tag_id)
        .group_by(Tag.id)
        .order_by(Tag.name.asc())
    )
    if prefix:
        stmt = stmt.where(Tag.name.ilike(f"{prefix}%"))

    rows = (await db.execute(stmt)).all()
    out: List[TagWithCount] = []
    for tag, count in rows:
        out.append(
            TagWithCount(
                id=tag.id,
                name=tag.name,
                created_at=tag.created_at,
                count=int(count),
            )
        )
    return out


@router.post(
    "",
    response_model=TagOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
    description="Create a tag. Tag name must be unique.",
)
# PUBLIC_INTERFACE
async def create_tag(payload: TagCreate, db: AsyncSession = Depends(get_db)) -> TagOut:
    """Create a new tag."""
    existing = (await db.execute(select(Tag).where(Tag.name == payload.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists")

    tag = Tag(name=payload.name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return TagOut.model_validate(tag)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag",
    description="Delete a tag by ID and remove its associations from notes.",
)
# PUBLIC_INTERFACE
async def delete_tag(tag_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a tag by UUID."""
    tag = (await db.execute(select(Tag).where(Tag.id == tag_id))).scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    await db.delete(tag)
    await db.commit()
    return None
