
from fastapi import FastAPI

from config.ethiopia import ETHIOPIA
from api.routes.rainfall import router as rainfall_router

# Create the FastAPI application FIRST
app = FastAPI(
    title="Dancing with the SARs API",
    description="Ethiopia rainfall and satellite analysis",
    version="0.1.0"
)


@app.get("/")
def home():
    return {
        "project": "Dancing with the SARs",
        "message": "Backend is running!",
        "status": "online"
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/region")
def get_region():
    return ETHIOPIA


# Register additional API routes AFTER creating app
app.include_router(rainfall_router, prefix="/api")
