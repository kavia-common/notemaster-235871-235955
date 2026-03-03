from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, constr


class TagBase(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=64) = Field(
        ...,
        description="Tag name (unique, case-insensitive behavior is not enforced; uniqueness is exact match).",
        examples=["work", "personal", "ideas"],
    )


class TagCreate(TagBase):
    pass


class TagOut(TagBase):
    id: uuid.UUID = Field(..., description="Tag ID (UUID).")
    created_at: datetime = Field(..., description="When the tag was created.")

    model_config = {"from_attributes": True}


class NoteBase(BaseModel):
    title: constr(strip_whitespace=True, min_length=1, max_length=200) = Field(
        ...,
        description="Note title.",
        examples=["Meeting notes", "Grocery list"],
    )
    content: str = Field(
        "",
        description="Markdown-capable note content.",
        examples=["# Header\nSome **bold** text."],
    )
    is_archived: bool = Field(False, description="Whether the note is archived.")


class NoteCreate(NoteBase):
    tag_names: List[constr(strip_whitespace=True, min_length=1, max_length=64)] = Field(
        default_factory=list,
        description="Optional list of tag names to attach (created if missing).",
        examples=[["work", "urgent"]],
    )


class NoteUpdate(BaseModel):
    title: Optional[constr(strip_whitespace=True, min_length=1, max_length=200)] = Field(None, description="New title.")
    content: Optional[str] = Field(None, description="New content.")
    is_archived: Optional[bool] = Field(None, description="New archived flag.")
    tag_names: Optional[List[constr(strip_whitespace=True, min_length=1, max_length=64)]] = Field(
        None,
        description="If provided, replaces the note's tags with exactly these tag names.",
    )


class NoteOut(NoteBase):
    id: uuid.UUID = Field(..., description="Note ID (UUID).")
    created_at: datetime = Field(..., description="When the note was created.")
    updated_at: datetime = Field(..., description="When the note was last updated.")
    tags: List[TagOut] = Field(default_factory=list, description="Tags attached to the note.")

    model_config = {"from_attributes": True}


class PaginatedNotes(BaseModel):
    items: List[NoteOut] = Field(..., description="Page of notes.")
    total: int = Field(..., description="Total number of notes matching the query.")
    limit: int = Field(..., description="Page size used for this query.")
    offset: int = Field(..., description="Offset used for this query.")


class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1, description="Free-text query to search in title/content.")
    tag: Optional[str] = Field(None, description="Optional tag name filter.")
    include_archived: bool = Field(False, description="Whether to include archived notes in results.")
    sort: str = Field("updated_at_desc", description="Sort order (updated_at_desc, updated_at_asc, created_at_desc, created_at_asc, title_asc, title_desc).")
    limit: int = Field(20, ge=1, le=100, description="Page size.")
    offset: int = Field(0, ge=0, description="Offset for pagination.")
