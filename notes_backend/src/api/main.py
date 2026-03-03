from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.notes import router as notes_router
from src.api.routers.search import router as search_router
from src.api.routers.tags import router as tags_router

openapi_tags = [
    {"name": "health", "description": "Service health and diagnostics."},
    {"name": "notes", "description": "CRUD operations for notes, including tag assignment."},
    {"name": "tags", "description": "Tag management and tag listing with usage counts."},
    {"name": "search", "description": "Search endpoints for querying notes."},
]

app = FastAPI(
    title="NoteMaster Backend API",
    description=(
        "REST API for NoteMaster: notes CRUD, tag management, and search.\n\n"
        "Database: PostgreSQL.\n"
        "Pagination: limit/offset.\n"
        "Sorting: updated_at/created_at/title."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router)
app.include_router(tags_router)
app.include_router(search_router)


@app.get("/", tags=["health"], summary="Health check", description="Simple health check endpoint.")
# PUBLIC_INTERFACE
def health_check():
    """Return a simple health response to indicate the service is running."""
    return {"message": "Healthy"}
