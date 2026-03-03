from __future__ import annotations

import uuid
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.db import get_db
from src.api.models import Note, Tag
from src.api.schemas import NoteCreate, NoteOut, NoteUpdate, PaginatedNotes

router = APIRouter(prefix="/notes", tags=["notes"])


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


async def _get_or_create_tags(db: AsyncSession, tag_names: Sequence[str]) -> List[Tag]:
    if not tag_names:
        return []

    normalized = [t.strip() for t in tag_names if t and t.strip()]
    if not normalized:
        return []

    # Load existing tags
    existing = (
        await db.execute(select(Tag).where(Tag.name.in_(normalized)))
    ).scalars().all()
    existing_by_name = {t.name: t for t in existing}

    # Create missing
    created: List[Tag] = []
    for name in normalized:
        if name in existing_by_name:
            continue
        tag = Tag(name=name)
        db.add(tag)
        created.append(tag)

    if created:
        await db.flush()  # assign IDs

    return [existing_by_name.get(n) or next(t for t in created if t.name == n) for n in normalized]


@router.post(
    "",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
    description="Create a note with optional initial tags. Missing tags are created automatically.",
)
# PUBLIC_INTERFACE
async def create_note(payload: NoteCreate, db: AsyncSession = Depends(get_db)) -> NoteOut:
    """Create a new note and return it."""
    tags = await _get_or_create_tags(db, payload.tag_names)
    note = Note(title=payload.title, content=payload.content, is_archived=payload.is_archived, tags=tags)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return NoteOut.model_validate(note)


@router.get(
    "",
    response_model=PaginatedNotes,
    summary="List notes",
    description="List notes with pagination and sorting. Optionally filter by tag and/or archived flag.",
)
# PUBLIC_INTERFACE
async def list_notes(
    db: AsyncSession = Depends(get_db),
    tag: Optional[str] = Query(None, description="Filter notes by tag name."),
    include_archived: bool = Query(False, description="Whether to include archived notes."),
    sort: str = Query("updated_at_desc", description="Sort order: updated_at_desc, updated_at_asc, created_at_desc, created_at_asc, title_asc, title_desc."),
    limit: int = Query(20, ge=1, le=100, description="Page size."),
    offset: int = Query(0, ge=0, description="Offset for pagination."),
) -> PaginatedNotes:
    """List notes with optional tag filter and sorting."""
    base_stmt = select(Note).options(selectinload(Note.tags))
    count_stmt = select(func.count(Note.id))

    if not include_archived:
        base_stmt = base_stmt.where(Note.is_archived.is_(False))
        count_stmt = count_stmt.where(Note.is_archived.is_(False))

    if tag:
        base_stmt = base_stmt.join(Note.tags).where(Tag.name == tag)
        count_stmt = count_stmt.select_from(Note).join(Note.tags).where(Tag.name == tag)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = base_stmt.order_by(_sort_clause(sort)).limit(limit).offset(offset)
    notes = (await db.execute(stmt)).scalars().unique().all()

    return PaginatedNotes(
        items=[NoteOut.model_validate(n) for n in notes],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{note_id}",
    response_model=NoteOut,
    summary="Get a note",
    description="Fetch a single note by ID.",
)
# PUBLIC_INTERFACE
async def get_note(note_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> NoteOut:
    """Get a note by UUID."""
    note = (
        await db.execute(select(Note).where(Note.id == note_id).options(selectinload(Note.tags)))
    ).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return NoteOut.model_validate(note)


@router.patch(
    "/{note_id}",
    response_model=NoteOut,
    summary="Update a note",
    description="Partially update a note. If tag_names is provided, it replaces tags.",
)
# PUBLIC_INTERFACE
async def update_note(note_id: uuid.UUID, payload: NoteUpdate, db: AsyncSession = Depends(get_db)) -> NoteOut:
    """Patch a note."""
    note = (
        await db.execute(select(Note).where(Note.id == note_id).options(selectinload(Note.tags)))
    ).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content
    if payload.is_archived is not None:
        note.is_archived = payload.is_archived
    if payload.tag_names is not None:
        note.tags = await _get_or_create_tags(db, payload.tag_names)

    await db.commit()
    await db.refresh(note)
    return NoteOut.model_validate(note)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    description="Delete a note by ID. Associated note-tag links are removed automatically.",
)
# PUBLIC_INTERFACE
async def delete_note(note_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a note by UUID."""
    note = (await db.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    await db.delete(note)
    await db.commit()
    return None
