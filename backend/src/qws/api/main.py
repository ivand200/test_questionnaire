from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

DIST_DIR = Path(__file__).resolve().parents[4] / "frontend" / "dist"


class LazyStaticFiles(StaticFiles):
    """StaticFiles that tolerates a missing directory: requests 404 until it exists."""

    async def check_config(self) -> None:
        pass


def create_app(dist_dir: Path = DIST_DIR) -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Mounted last so every /api/* route above wins over the static files.
    # dist may not exist yet; files are looked up per request, so a build made
    # after startup is served without a restart.
    app.mount("/", LazyStaticFiles(directory=dist_dir, html=True, check_dir=False))

    return app


app = create_app()
