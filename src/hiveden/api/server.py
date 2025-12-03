from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hiveden.api.routers import config, docker, info, lxc, shares, shell, pkgs, storage

app = FastAPI(
    title="Hiveden API",
    description="An API for managing your personal server.",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

app.include_router(config.router)
app.include_router(docker.router)
app.include_router(info.router)
app.include_router(lxc.router)
app.include_router(shares.router)
app.include_router(shell.router)
app.include_router(pkgs.router)
app.include_router(storage.router)
