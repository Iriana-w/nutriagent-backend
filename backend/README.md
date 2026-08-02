# ============================================================================
# NutriAgent Backend — Backend README
# ============================================================================

# NutriAgent Backend

AI-powered health diet recommendation system for programmers.
Built with **Python 3.12**, **FastAPI**, **PostgreSQL + pgvector**, **Redis**, and **LangGraph**.

## Quick Start

### 1. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your database, Redis, and LLM API keys
```

### 3. Set Up Database
```bash
# Start PostgreSQL + Redis via Docker
docker run -d --name nutriagent-pg -p 5432:5432 \
  -e POSTGRES_USER=nutriagent -e POSTGRES_PASSWORD=nutriagent \
  -e POSTGRES_DB=nutriagent pgvector/pgvector:pg16

docker run -d --name nutriagent-redis -p 6379:6379 redis:7-alpine

# Run migrations
cd backend
alembic upgrade head

# Seed initial data (food categories, etc.)
psql postgresql://nutriagent:nutriagent@localhost:5432/nutriagent -f ../schema.sql
```

### 4. Run Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open API Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure
```
backend/
├── app/
│   ├── api/v1/         # REST API routes
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response schemas
│   ├── services/       # Business logic layer
│   ├── agents/         # LangGraph AI agents (recommendation engine)
│   ├── tools/          # Agent tools (nutrition calc, food search, etc.)
│   ├── core/           # Security, exceptions, middleware
│   ├── prompts/        # LLM prompt templates
│   ├── config.py       # Application settings
│   ├── database.py     # Async DB connection
│   ├── redis.py        # Redis client & caching
│   └── main.py         # FastAPI application entry point
├── alembic/            # Database migrations
├── tests/              # Test suite
├── requirements.txt
├── Dockerfile
└── .env.example
```

## API Overview

| Group | Endpoints |
|-------|-----------|
| Auth | POST /register, /login, /refresh |
| Users | GET/PATCH /me, health-profile, goals, allergens, preferences |
| Recommendations | POST /meal, /daily, /weekly, /scenario, feedback |
| Food Logs | CRUD /food-logs, photo recognition |
| Delivery | GET /search, /merchants/:name/menu |
| Nutrition | GET /dashboard, /report/weekly, /report/monthly |
| Chat | Sessions & messages management |

## Tech Stack
- **Web**: FastAPI 0.115+, Uvicorn
- **DB**: PostgreSQL 16 + pgvector (async SQLAlchemy 2.0 + asyncpg)
- **Cache**: Redis 7 (caching, sessions, rate limiting)
- **AI**: LangGraph + LangChain + OpenAI/Claude API
- **Auth**: JWT (python-jose) + bcrypt
- **Validation**: Pydantic 2.x

## License
Proprietary — NutriAgent Team
