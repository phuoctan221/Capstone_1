from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.routers import (
    auth_router,
    vocabulary_router,
    learning_router,
    lesson_router,
    progress_router,
)

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(10):
        try:
            await connect_to_mongo()
            logger.info("MongoDB connected")
            break
        except Exception as e:
            if attempt == 9:
                raise
            logger.warning(
                f"MongoDB connection failed ({e}), retrying in 3s... [{attempt+1}/10]"
            )
            await asyncio.sleep(3)
    yield
    await close_mongo_connection()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(vocabulary_router.router)
app.include_router(learning_router.router)
app.include_router(lesson_router.router)
app.include_router(progress_router.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
