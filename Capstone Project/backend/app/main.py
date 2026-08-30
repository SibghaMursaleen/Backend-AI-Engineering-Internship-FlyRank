from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import router as api_router

from app.jobs.scheduler import scheduler

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for Usage Metering and Billing Engine",
    version="1.0.0"
)

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bind background scheduler to server lifecycle events
@app.on_event("startup")
def start_scheduler():
    scheduler.start()
    print("Background scheduler started successfully.")

@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()
    print("Background scheduler shut down successfully.")

# Register our route controllers
app.include_router(api_router)

@app.get("/")
def read_root():
    return {
        "message": f"Welcome to the {settings.PROJECT_NAME}",
        "docs": "/docs",
        "health": "/health"
    }
