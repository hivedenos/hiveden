import traceback
from fastapi import APIRouter, HTTPException
from fastapi.logger import logger

from hiveden.db.session import get_db_manager
from hiveden.api.dtos import (
    SuccessResponse, 
    DatabaseListResponse, 
    DatabaseUserListResponse, 
    DatabaseCreateRequest
)

router = APIRouter(prefix="/db", tags=["Database"])

@router.get("/databases", response_model=DatabaseListResponse)
def list_databases():
    """List all databases."""
    try:
        manager = get_db_manager()
        dbs = manager.list_databases()
        return DatabaseListResponse(data=dbs)
    except Exception as e:
        logger.error(f"Error listing databases: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/databases", response_model=SuccessResponse)
def create_database(req: DatabaseCreateRequest):
    """Create a new database."""
    try:
        manager = get_db_manager()
        manager.create_database(req.name, req.owner)
        return SuccessResponse(message=f"Database '{req.name}' created successfully.")
    except Exception as e:
        logger.error(f"Error creating database {req.name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users", response_model=DatabaseUserListResponse)
def list_users():
    """List all database users."""
    try:
        manager = get_db_manager()
        users = manager.list_users()
        return DatabaseUserListResponse(data=users)
    except Exception as e:
        logger.error(f"Error listing users: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))