# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cognitex v2 - AI-Driven Personal Productivity System

### Project Goals
- Extract tasks and actions from emails and meeting transcripts
- Synthesize information from calendar, tasks (Todoist), and communications
- Identify optimal next actions considering neurodivergent needs
- Map personal networks and uncover social opportunities
- Guide progress toward short/medium/long-term goals

## Current Development Phase

**Phase 0: Foundation Setup** ✓ Complete
- Project structure created
- Dependencies defined
- Git repository initialized

**Phase 1: Core Application Skeleton** ✓ Complete
- Configuration management with Pydantic settings
- Message-based orchestrator for agent communication
- Base agent abstract class with standard interface
- FastAPI application with lifespan events
- CORS middleware and health check endpoints
- Logging infrastructure

**Phase 2: Authentication & User Management** ✓ Complete
- Firebase client for Firestore database interactions
- Google OAuth2 authentication flow
- JWT token creation and verification
- User session management
- Authentication API endpoints
- Basic login UI with Google Sign-In button
- Static file serving for frontend

**Phase 3: First Tool-Based Agent (Email)** ✓ Complete
- Google API service clients for authenticated access
- Gmail tools as stateless functions with LLM-friendly docstrings
- EmailAgent with LLM reasoning capabilities
- LLM service with tool calling support
- Email API routes for agent operations
- Dashboard UI with email summarization features
- Agent registration with orchestrator

**Next: Phase 4 - Expand Agent Capabilities**
Add more agents (Calendar, Tasks) and enhance synthesis capabilities.

## Architecture Decisions

### Core Components
1. **Agents**: Autonomous AI components that perform specific tasks
2. **Tools**: Stateless functions that agents use (API calls, data processing)
3. **Orchestrator**: Manages agent scheduling and coordination
4. **Model Router**: Selects appropriate LLM based on task requirements

### Technology Stack
- **Backend**: FastAPI (async Python web framework)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Firebase Auth + Google OAuth
- **AI/LLM**: Anthropic Claude (primary), OpenAI (secondary)
- **Task Queue**: APScheduler for background jobs
- **Frontend**: Jinja2 templates with HTMX for interactivity

## Development Workflow

### Running Locally
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Setup
```bash
# After creating models, initialize Alembic
alembic init alembic

# Generate initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

### Testing Strategy
```bash
# Unit tests for individual components
pytest tests/unit/

# Integration tests for agent workflows
pytest tests/integration/

# End-to-end tests for complete flows
pytest tests/e2e/
```

## Implementation Guidelines

### Agent Development
Each agent should:
- Have a single, clear responsibility
- Use dependency injection for tools
- Implement retry logic for external API calls
- Log all significant actions
- Return structured `AgentResult` objects

### API Design
- RESTful endpoints under `/api/v1/`
- WebSocket endpoint for real-time updates at `/ws`
- Health check at `/health`
- OpenAPI docs at `/docs`

### Security Considerations
- All external API keys in environment variables
- User data encrypted at rest
- Rate limiting on all endpoints
- CORS configured for production domain only
- SQL injection prevention via parameterized queries

## File Naming Conventions
- Agents: `{name}_agent.py` (e.g., `email_analysis_agent.py`)
- Tools: `{name}_tool.py` (e.g., `gmail_tool.py`)
- Models: `{entity}_model.py` (e.g., `user_model.py`)
- Services: `{name}_service.py` (e.g., `auth_service.py`)

## Environment Configuration

Required `.env` variables:
```
# Core
SECRET_KEY=           # Generate with: openssl rand -hex 32
ENVIRONMENT=          # development | production

# Database
DATABASE_URL=         # postgresql+asyncpg://...

# Firebase
FIREBASE_CREDENTIALS_PATH=

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# AI Models
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Optional
LOG_LEVEL=INFO
REDIS_URL=            # If using Redis for caching
```

## Common Tasks

### Add New Agent
1. Create agent file in `app/agents/`
2. Inherit from `BaseAgent`
3. Register in `app/agents/__init__.py`
4. Add tests in `tests/agents/`

### Add New API Endpoint
1. Create router in `app/api/`
2. Include router in `app/main.py`
3. Add request/response models in `app/models/`
4. Document in OpenAPI schema

### Deploy Changes
1. Run tests: `pytest`
2. Check linting: `ruff check app/`
3. Format code: `black app/`
4. Commit with descriptive message
5. Tag version if releasing

## Debugging Tips
- Check `logs/app.log` for application logs
- Use `--reload` flag for auto-reloading during development
- Enable SQL echo for database debugging: `echo=True` in engine
- Use `import pdb; pdb.set_trace()` for breakpoints
- Monitor agent performance in `agent_runs` table