#!/usr/bin/env bash
# scripts/setup.sh
# ─────────────────────────────────────────────────────────────
# One-shot local dev setup:
#   1. Create virtualenv & install deps
#   2. Copy .env.example → .env
#   3. Start Postgres + Redis via Docker
#   4. Run DB migrations (create_all via Python)
#   5. Seed sample data
#   6. Start the FastAPI dev server
# ─────────────────────────────────────────────────────────────
set -euo pipefail

BOLD='\033[1m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "\n${BOLD}═══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Enterprise AI Knowledge & Decision Assistant${NC}"
echo -e "${BOLD}  Setup Script${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════${NC}\n"

# ── 1. Python virtualenv ─────────────────────────────────────
info "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    success "Virtual environment created at .venv/"
else
    warn "Virtual environment already exists — skipping creation"
fi

source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
success "Python dependencies installed"

# ── 2. Environment file ──────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    success ".env file created from template"
    warn "⚠️  Edit .env and add your ANTHROPIC_API_KEY before starting"
else
    warn ".env already exists — not overwriting"
fi

# ── 3. Docker services ───────────────────────────────────────
info "Starting Postgres and Redis via Docker..."
if command -v docker &>/dev/null && command -v docker compose &>/dev/null; then
    docker compose up -d postgres redis
    info "Waiting for services to be healthy..."
    sleep 8
    success "Postgres and Redis started"
else
    warn "Docker not found — assuming Postgres/Redis are already running locally"
fi

# ── 4. Database schema ───────────────────────────────────────
info "Creating database schema..."
python3 - <<'PYEOF'
import asyncio, sys, os
sys.path.insert(0, os.getcwd())
os.environ.setdefault("APP_ENV", "development")
from utils.database import create_all_tables
asyncio.run(create_all_tables())
print("  Schema created successfully")
PYEOF
success "Database schema ready"

# ── 5. Seed sample data ──────────────────────────────────────
info "Seeding sample enterprise data..."
python3 scripts/seed_data.py
success "Sample data seeded"

# ── 6. Frontend deps ─────────────────────────────────────────
if command -v npm &>/dev/null; then
    info "Installing frontend dependencies..."
    cd frontend && npm install --silent && cd ..
    success "Frontend dependencies installed"
else
    warn "npm not found — skipping frontend setup"
fi

echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup complete! 🚀${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Start backend:${NC}  uvicorn api_gateway.main:app --reload --port 8000"
echo -e "  ${BOLD}Start frontend:${NC} cd frontend && npm run dev"
echo -e "  ${BOLD}API docs:${NC}       http://localhost:8000/docs"
echo -e "  ${BOLD}App UI:${NC}         http://localhost:3000"
echo ""
