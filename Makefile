.PHONY: dev backend web setup test lint

dev:
	@command -v concurrently >/dev/null 2>&1 || npx --yes concurrently --version >/dev/null 2>&1 || true
	@echo "Starting backend (:8000) and web (:3000) in parallel — Ctrl-C to stop both"
	@npx --yes concurrently --kill-others --names backend,web --prefix-colors blue,magenta \
		"cd backend && uv run examcraft-server" \
		"cd web && npm run dev"

backend:
	cd backend && uv run examcraft-server

web:
	cd web && npm run dev

setup:
	@echo "1. brew install poppler libreoffice"
	@echo "2. cp .env.example .env  &&  edit OPENAI_API_KEY + EXAMCRAFT_SESSION_SECRET"
	cd backend && uv sync
	cd web && npm install

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check app tests
