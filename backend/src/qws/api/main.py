from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

DIST_DIR = Path(__file__).resolve().parents[4] / "frontend" / "dist"


def create_app(dist_dir: Path = DIST_DIR) -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Mounted last so every /api/* route above wins over the static files.
    if dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=dist_dir, html=True))

    return app


app = create_app()
