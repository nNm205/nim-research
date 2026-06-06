from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.utils.logger import logger 
from app.routes import (
    auth, 
    projects, 
    documents, 
    research,
    analysis,
    reports,
    knowledge_base,
    notifications,
)
from app.services.stale_recovery import recover_stale_sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Recover any zombie ``running`` rows from a previous crash before
    accepting traffic. Without this the FE keeps showing live progress
    panels for sessions whose background task died with the previous
    process — the user has to manually delete the session to clear it.
    """
    try:
        await recover_stale_sessions()
    except Exception as e:
        logger.error(f"Startup recovery failed: {e}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    """Log the raw request body alongside any 422 so the FE-side error
    message is actionable. FastAPI's default just returns the pydantic
    ``errors()`` payload to the client without any server-side log,
    which makes diagnosing field-level problems painful."""
    try:
        body = await request.body()
    except Exception:
        body = b""
    logger.warning(
        f"422 Unprocessable Entity at {request.method} {request.url.path}: "
        f"errors={exc.errors()} body={body[:1000]!r}"
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(documents.ingest_router)
app.include_router(documents.meta_router)
app.include_router(documents.all_router)
app.include_router(research.router)
app.include_router(analysis.router)
app.include_router(reports.router)
app.include_router(knowledge_base.router)
app.include_router(notifications.router)

@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    
    return {
        "message": "Backend Running"
    }