.PHONY: dev dev-api dev-web start reset test types record checks

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	cd backend && uv run uvicorn qws.api.main:app --reload --port 8000

dev-web:
	cd frontend && pnpm exec vite

# The finished app on one port: builds the Frontend, then the Backend serves it and /api/*.
# Replay mode unless MODEL_MODE=real is set in the environment.
start:
	cd frontend && pnpm exec vite build
	cd backend && uv run uvicorn qws.api.main:app --port 8000

# Delete the Database file and its -wal and -shm files (DB_PATH if set, else backend/qws.db).
# A relative DB_PATH counts from backend/, as it does for the app. No file is not an error.
reset:
	cd backend && db="$${DB_PATH:-qws.db}" && rm -f "$$db" "$$db-wal" "$$db-shm"

test:
	cd frontend && pnpm exec tsc --noEmit
	cd frontend && pnpm exec vite build
	cd backend && uv run pytest

types:
	(cd backend && uv run python -c "import json; from qws.api.main import app; print(json.dumps(app.openapi()))") > frontend/openapi.tmp.json; \
	status=$$?; \
	if [ $$status -eq 0 ]; then (cd frontend && pnpm exec openapi-typescript openapi.tmp.json -o src/api/api.d.ts); status=$$?; fi; \
	rm -f frontend/openapi.tmp.json; \
	exit $$status

# Real model calls for the recording list; needs OPENAI_API_KEY (from the shell or .env).
record:
	cd backend && set -a && { [ ! -f ../.env ] || . ../.env; } && set +a && uv run python -m qws.services.recorder

# The five checks and Case 6 in replay mode, no key; writes docs/check-results.md.
# Use another Reference file with: make checks CASES=path/to/copy.json
checks:
	cd backend && uv run python -m qws.services.checks $(if $(CASES),$(abspath $(CASES)))
