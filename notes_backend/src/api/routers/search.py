from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.db import get_db
from src.api.models import Note, Tag
from src.api.schemas import PaginatedNotes, NoteOut

router = APIRouter(prefix="/search", tags=["search"])


def _sort_clause(sort: str):
    sort_map = {
        "updated_at_desc": desc(Note.updated_at),
        "updated_at_asc": asc(Note.updated_at),
        "created_at_desc": desc(Note.created_at),
        "created_at_asc": asc(Note.created_at),
        "title_asc": asc(Note.title),
        "title_desc": desc(Note.title),
    }
    return sort_map.get(sort, desc(Note.updated_at))


@router.get(
    "",
    response_model=PaginatedNotes,
    summary="Search notes",
    description="Full-text search notes by query string (searches title and content), with optional tag filter and pagination.",
)
# PUBLIC_INTERFACE
async def search_notes(
    q: str = Query(..., min_length=1, description="Search query (full-text)."),
    db: AsyncSession = Depends(get_db),
    tag: Optional[str] = Query(None, description="Optional tag filter by name."),
    include_archived: bool = Query(False, description="Whether to include archived notes."),
    sort: str = Query("updated_at_desc", description="Sort order: updated_at_desc, updated_at_asc, created_at_desc, created_at_asc, title_asc, title_desc."),
    limit: int = Query(20, ge=1, le=100, description="Page size."),
    offset: int = Query(0, ge=0, description="Offset for pagination."),
) -> PaginatedNotes:
    """Search notes using PostgreSQL full-text search."""
    ts_query = func.plainto_tsquery("english", q)

    base = select(Note).options(selectinload(Note.tags))
    count = select(func.count(Note.id))

    # full-text match in title/content
    match_expr = func.to_tsvector("english", func.coalesce(Note.title, "") + " " + func.coalesce(Note.content, "")).op("@@")(ts_query)

    base = base.where(match_expr)
    count = count.where(match_expr)

    if not include_archived:
        base = base.where(Note.is_archived.is_(False))
        count = count.where(Note.is_archived.is_(False))

    if tag:
        base = base.join(Note.tags).where(Tag.name == tag)
        count = count.select_from(Note).join(Note.tags).where(Tag.name == tag).where(match_expr)

    total = (await db.execute(count)).scalar_one()
    stmt = base.order_by(_sort_clause(sort)).limit(limit).offset(offset)
    notes = (await db.execute(stmt)).scalars().unique().all()

    return PaginatedNotes(
        items=[NoteOut.model_validate(n) for n in notes],
        total=int(total),
        limit=limit,
        offset=offset,
    )
