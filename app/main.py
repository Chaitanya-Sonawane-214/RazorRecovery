"""
Phase 6: FastAPI entry point.
Serves the batch results API and the static frontend dashboard.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import batch

app = FastAPI(title="RazorRecovery API")

# Allow the frontend (served separately or from same origin) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for a hackathon demo; restrict in real production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batch.router, prefix="/api")

# Serve the frontend as static files at the root
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")