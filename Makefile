.PHONY: dev dev-api dev-web test types

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	cd backend && uv run uvicorn qws.api.main:app --reload --port 8000

dev-web:
	cd frontend && pnpm exec vite

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
