"""FastAPI entry point for the TIA backend."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import APP_NAME, APP_VERSION
from app.core.logging_config import configure_logging

configure_logging()

app = FastAPI(title=APP_NAME, version=APP_VERSION)


class HealthResponse(BaseModel):
    """Public health response for the local backend process."""

    status: Literal["healthy"]
    app: str
    version: str


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """Report that the backend process is responding."""
    return HealthResponse(status="healthy", app=APP_NAME, version=APP_VERSION)
