# FraudShield — convenience commands for local development.
# Run `make help` to see everything available.

.PHONY: help api-install api-dev api-test api-lint web-install web-dev web-test web-lint test-all lint-all

help:
	@echo "FraudShield monorepo commands:"
	@echo ""
	@echo "  make api-install   Install backend dependencies"
	@echo "  make api-dev       Run backend API locally (port 8000)"
	@echo "  make api-test      Run backend test suite (173 tests)"
	@echo "  make api-lint      Lint backend code"
	@echo ""
	@echo "  make web-install   Install frontend dependencies"
	@echo "  make web-dev       Run frontend locally (port 3000)"
	@echo "  make web-test      Type-check + lint + build frontend"
	@echo "  make web-lint      Lint frontend code"
	@echo ""
	@echo "  make test-all      Run both test suites"
	@echo "  make lint-all      Lint both apps"

api-install:
	cd apps/api && pip install -r requirements.txt

api-dev:
	cd apps/api && uvicorn src.api.main:app --reload --port 8000

api-test:
	cd apps/api && ENVIRONMENT=development pytest tests/ -v

api-lint:
	cd apps/api && ruff check src/ config/ --select=E,W,F --ignore=E501

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

web-test:
	cd apps/web && npx tsc --noEmit && npx next lint && npm run build

web-lint:
	cd apps/web && npx next lint

test-all: api-test web-test

lint-all: api-lint web-lint
