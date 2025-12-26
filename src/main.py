from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .core.config import settings
from .api.routes import router

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Computer vision system for detecting tool presence in industrial toolkits",
)

# Include API routes
app.include_router(router)

# Static files directory
static_dir = Path(__file__).parent.parent / "static"
static_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the main web UI."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Toolkit Processor API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
