"""API router for storage operations."""

from fastapi.logger import logger
from fastapi import APIRouter, HTTPException
from typing import List

from hiveden.api.dtos import (
    DiskListResponse,
    DiskDetailResponse,
    StorageStrategyListResponse,
    StorageStrategyApplyResponse,
    ErrorResponse,
    SuccessResponse
)
from hiveden.storage.manager import StorageManager
from hiveden.storage.models import Disk, StorageStrategy, MountRequest

router = APIRouter(prefix="/storage", tags=["Storage"])
manager = StorageManager()

@router.post(
    "/mount",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)
def mount_partition(request: MountRequest):
    """
    Mounts a disk partition.
    """
    try:
        mount_point = manager.mount_partition(
            device=request.device,
            automatic=request.automatic,
            mount_name=request.mount_name
        )
        return SuccessResponse(message=f"Device {request.device} mounted at {mount_point}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error mounting device: {e}")
        import traceback
        logger.error(f"Error mounting device: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/devices", 
    response_model=DiskListResponse,
    responses={500: {"model": ErrorResponse, "description": "Internal Server Error"}}
)
def list_devices():
    """
    List all block devices on the system.
    """
    try:
        disks = manager.list_disks()
        return DiskListResponse(data=[d.dict() for d in disks])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/devices/{device_name}", 
    response_model=DiskDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Device not found"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)
def get_device_details(device_name: str):
    """
    Get detailed information for a specific disk (including SMART data).
    """
    try:
        details = manager.get_disk_details(device_name)
        if not details:
            raise HTTPException(status_code=404, detail="Device not found")
        return DiskDetailResponse(data=details.dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/strategies", 
    response_model=StorageStrategyListResponse,
    responses={500: {"model": ErrorResponse, "description": "Internal Server Error"}}
)
def list_strategies():
    """
    Suggests storage configuration strategies based on currently unused disks.
    """
    try:
        strategies = manager.get_strategies()
        return StorageStrategyListResponse(data=[s.dict() for s in strategies])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post(
    "/apply", 
    response_model=StorageStrategyApplyResponse,
    responses={500: {"model": ErrorResponse, "description": "Internal Server Error"}}
)
async def apply_strategy(strategy: StorageStrategy):
    """
    Applies a storage strategy. Starts a background job.
    """
    try:
        job_id = manager.apply_strategy(strategy)
        return StorageStrategyApplyResponse(
            message="Storage configuration started",
            data={"job_id": job_id}
        )
    except Exception as e:
        logger.error(f"Error applying storage strategy: {e}")

        import traceback
        logger.error(f"Error applying storage strategy: {e}\n{traceback.format_exc()}")

        raise HTTPException(status_code=500, detail=str(e))
