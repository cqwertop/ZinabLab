import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from core.paths import BASE_DIR

load_dotenv(BASE_DIR / ".env")

from routers.chat import router as chat_router
from routers.climate import router as climate_router
from core import http
from ml.forecast import engine
from services import drivers, openmeteo, status


async def warm_up():
    for task in (drivers.snapshot(), status.national_pulse(), openmeteo.regional_outlook(), engine.ensure()):
        try:
            await task
        except Exception as error:
            print(f"warm-up step failed: {error}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    job = asyncio.create_task(warm_up())
    yield
    job.cancel()
    await http.close()


app = FastAPI(
    title="Zinab Lab API",
    description="Live rainfall tracking, drought attribution and forecasting for Ethiopia. NASA Space Apps Challenge: Dancing with the SARs.",
    version="2.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in os.environ.get("ZINAB_CORS_ORIGINS", "http://localhost:4321,http://127.0.0.1:4321").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.get("/")
def home():
    return {"project": "Zinab Lab", "challenge": "Dancing with the SARs", "status": "online", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "healthy", "modelReady": engine.ready}


app.include_router(climate_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
