from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import logging
import sys
from pathlib import Path
from typing import Optional

from app.config import settings
from app.orchestrator import SimpleOrchestrator
from app.database.firebase_client import firebase_client
from app.api import auth_routes, email_routes, oauth_routes, insights_routes, goal_routes
from app.agents.email_agent import EmailAgent
from app.agents.proactive_synthesis_agent import ProactiveSynthesisAgent
from app.agents.goal_agent import GoalAgent
from app.services.scheduler import SchedulerService

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logs directory if it doesn't exist
if settings.LOG_FILE:
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(exist_ok=True, parents=True)
    file_handler = logging.FileHandler(settings.LOG_FILE)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)

# Global instances
orchestrator: Optional[SimpleOrchestrator] = None
scheduler: Optional[SchedulerService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle - startup and shutdown events
    """
    global orchestrator
    
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.APP_ENV}")
    
    # Initialize orchestrator
    orchestrator = SimpleOrchestrator()
    logger.info("Orchestrator initialized")
    
    # Start orchestrator message processing loop as background task
    import asyncio
    orchestrator_task = asyncio.create_task(orchestrator.run())
    logger.info("Orchestrator message processing started")
    
    # Initialize Firebase
    try:
        firebase_client.initialize()
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.warning(f"Firebase initialization failed: {e}")
        logger.info("Running without Firebase - authentication features will be limited")
    
    # Register agents
    email_agent = EmailAgent()
    orchestrator.register_agent(email_agent.name, email_agent)
    logger.info(f"Registered agent: {email_agent.name}")
    
    synthesis_agent = ProactiveSynthesisAgent()
    orchestrator.register_agent(synthesis_agent.name, synthesis_agent)
    logger.info(f"Registered agent: {synthesis_agent.name}")
    
    goal_agent = GoalAgent()
    orchestrator.register_agent(goal_agent.name, goal_agent)
    logger.info(f"Registered agent: {goal_agent.name}")
    
    # Initialize and start scheduler
    global scheduler
    scheduler = SchedulerService(orchestrator=orchestrator)
    scheduler.start()
    logger.info("Scheduler service started")
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Starting application shutdown")
    
    if scheduler:
        scheduler.stop()
        logger.info("Scheduler stopped")
    
    if orchestrator:
        orchestrator.stop()
        logger.info("Orchestrator stopped")
    
    # TODO: Cleanup resources
    # TODO: Close database connections
    
    logger.info("Application shutdown complete")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-driven personal productivity system",
    lifespan=lifespan,
    debug=settings.DEBUG
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    """
    global orchestrator
    
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV
    }
    
    # Add orchestrator status if available
    if orchestrator:
        health_status["orchestrator"] = orchestrator.get_stats()
    
    return health_status

# API info endpoint
@app.get("/api")
async def api_info():
    """
    API information endpoint
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "AI-driven personal productivity system",
        "docs": "/docs",
        "health": "/health"
    }

# Orchestrator status endpoint
@app.get("/api/v1/orchestrator/status")
async def orchestrator_status():
    """
    Get orchestrator status and statistics
    """
    global orchestrator
    
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    return orchestrator.get_stats()

# List registered agents
@app.get("/api/v1/agents")
async def list_agents():
    """
    List all registered agents
    """
    global orchestrator
    
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    agents = []
    for agent_name in orchestrator.list_agents():
        agent = orchestrator.get_agent(agent_name)
        if agent and hasattr(agent, 'get_stats'):
            agents.append(agent.get_stats())
        else:
            agents.append({"name": agent_name, "status": "unknown"})
    
    return {"agents": agents, "count": len(agents)}

# Include API routes
app.include_router(auth_routes.router)
app.include_router(email_routes.router)
app.include_router(oauth_routes.router)
app.include_router(insights_routes.router)
app.include_router(goal_routes.router)

# Mount static files
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")

# Serve the main UI
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main UI"""
    ui_path = Path("app/ui/templates/index.html")
    if ui_path.exists():
        with open(ui_path, "r") as f:
            content = f.read()
            # Replace Google Client ID placeholder
            content = content.replace("YOUR_GOOGLE_CLIENT_ID", settings.GOOGLE_CLIENT_ID)
            return HTMLResponse(content=content)
    else:
        return HTMLResponse(content="<h1>Cognitex UI not found</h1>")

# Serve insights dashboard
@app.get("/insights", response_class=HTMLResponse)
async def serve_insights():
    """Serve the insights dashboard"""
    ui_path = Path("app/ui/templates/insights_dashboard.html")
    if ui_path.exists():
        with open(ui_path, "r") as f:
            content = f.read()
            return HTMLResponse(content=content)
    else:
        return HTMLResponse(content="<h1>Insights dashboard not found</h1>")

# Serve test page
@app.get("/test", response_class=HTMLResponse)
async def serve_test():
    """Serve the test page"""
    test_path = Path("test_auth_api.html")
    if test_path.exists():
        with open(test_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Test page not found</h1>")

# Serve dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the dashboard page"""
    dashboard_path = Path("app/ui/templates/dashboard.html")
    if dashboard_path.exists():
        with open(dashboard_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Dashboard not found</h1>")

# Serve insights dashboard
@app.get("/insights", response_class=HTMLResponse)
async def serve_insights():
    """Serve the insights dashboard page"""
    insights_path = Path("app/ui/templates/insights_dashboard.html")
    if insights_path.exists():
        with open(insights_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Insights dashboard not found</h1>")

# Serve wise advisor dashboard
@app.get("/advisor", response_class=HTMLResponse)
async def serve_advisor():
    """Serve the wise advisor dashboard page"""
    advisor_path = Path("app/ui/templates/wise_advisor_dashboard.html")
    if advisor_path.exists():
        with open(advisor_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Advisor dashboard not found</h1>")

# Serve goals dashboard
@app.get("/goals", response_class=HTMLResponse)
async def serve_goals():
    """Serve the goals dashboard page"""
    goals_path = Path("app/ui/templates/goals_dashboard.html")
    if goals_path.exists():
        with open(goals_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Goals dashboard not found</h1>")

# TODO: Add more API routes for agents
# TODO: Add WebSocket endpoint for real-time updates

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower()
    )