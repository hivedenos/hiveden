"""API router for storage operations."""

from fastapi import APIRouter, HTTPException
from typing import List

from hiveden.api.dtos import DataResponse
from hiveden.storage.manager import StorageManager
from hiveden.storage.models import Disk, StorageStrategy

router = APIRouter(prefix="/storage", tags=["Storage"])
manager = StorageManager()

@router.get("/devices", response_model=DataResponse)
def list_devices():
    """
    List all block devices on the system.
    """
    try:
        disks = manager.list_disks()
        return DataResponse(data=[d.dict() for d in disks])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategies", response_model=DataResponse)
def list_strategies():
    """
    Suggests storage configuration strategies based on currently unused disks.
    """
    try:
        strategies = manager.get_strategies()
        return DataResponse(data=[s.dict() for s in strategies])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
