# Cognitex v2

AI-driven personal productivity system that intelligently synthesizes information from multiple sources (emails, calendars, tasks, meeting transcripts) to identify optimal next actions and uncover social networking opportunities.

## Architecture

Built with an "AI agents with tools" paradigm at its core:
- **Stateless Tools, Stateful Agents**: Long-running agents maintain context and orchestrate tasks
- **Proactive Synthesis**: Background scheduler triggers continuous data analysis
- **Model Ensemble**: Intelligent routing to optimal LLMs based on task requirements
- **Insights-First**: Focus on synthesized insights rather than raw data

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL (optional, SQLite used by default in development)
- Virtual environment support

### Installation

1. Clone the repository and navigate to the project directory:
```bash
cd cognitex
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the environment template and configure:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the application:
```bash
uvicorn app.main:app --reload
```

The application will be available at http://localhost:8000

## API Documentation

Once running, you can access:
- Interactive API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Orchestrator status: http://localhost:8000/api/v1/orchestrator/status
- List agents: http://localhost:8000/api/v1/agents

## Project Structure

```
cognitex/
├── app/
│   ├── agents/          # AI agents for various tasks
│   ├── api/             # FastAPI endpoints
│   ├── auth/            # Authentication (Firebase/OAuth)
│   ├── config/          # Configuration management
│   ├── database/        # Database models and migrations
│   ├── orchestrator/    # Task orchestration and scheduling
│   ├── prompts/         # LLM prompt templates
│   ├── services/        # External service integrations
│   └── ui/              # Web interface
├── tests/               # Test suite
├── logs/                # Application logs
├── requirements.txt     # Python dependencies
├── .env                 # Environment configuration
└── README.md           # This file
```

## Development Status

### Phase 1: Core Application Skeleton ✅
- Configuration management system
- Message-based orchestrator
- Base agent architecture
- FastAPI application with health checks
- CORS and logging setup

### Next Phases
- Phase 2: Authentication (Firebase + Google OAuth)
- Phase 3: Database schema and models
- Phase 4: First functional agent (Email Analysis)
- Phase 5: Calendar and task integration
- Phase 6: Synthesis engine
- Phase 7: Insights dashboard

## Configuration

Key environment variables:
- `APP_ENV`: Environment (development/production)
- `SECRET_KEY`: Application secret key
- `DATABASE_URL`: Database connection string
- `GOOGLE_CLIENT_ID/SECRET`: OAuth credentials
- `ANTHROPIC_API_KEY`: Claude API access
- `LOG_LEVEL`: Logging verbosity

## Testing

Run tests with:
```bash
pytest
```

## License

Private project - all rights reserved.