"""API router for storage operations."""

from fastapi.logger import logger
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import List

from hiveden.api.dtos import (
    DiskListResponse,
    DiskDetailResponse,
    StorageStrategyListResponse,
    StorageStrategyApplyResponse,
    ErrorResponse,
    SuccessResponse,
    RaidAddDiskRequest
)
from hiveden.storage.manager import StorageManager
from hiveden.storage.models import Disk, StorageStrategy, MountRequest

router = APIRouter(prefix="/storage", tags=["Storage"])
manager = StorageManager()

@router.post(
    "/raid/{md_device_name}/add-disk",
    response_model=StorageStrategyApplyResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)
def add_disk_to_raid(md_device_name: str, request: RaidAddDiskRequest):
    """
    Add a disk to an existing RAID array, optionally changing the RAID level.
    """
    try:
        # Assuming md_device_name is like 'md0', we prepend /dev/
        md_device = f"/dev/{md_device_name}"
        job_id = manager.add_disk_to_raid(md_device, request.device_path, request.target_raid_level)
        return StorageStrategyApplyResponse(
            message="RAID expansion initiated successfully",
            data={"job_id": job_id}
        )
    except Exception as e:
        logger.error(f"Error adding disk to RAID: {e}")
        import traceback
        logger.error(f"Error adding disk to RAID: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

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
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(message=str(e)).model_dump()
        )
    except Exception as e:
        logger.error(f"Error mounting device: {e}")
        import traceback
        logger.error(f"Error mounting device: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

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
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

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
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(message="Device not found").model_dump()
            )
        return DiskDetailResponse(data=details.dict())
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

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
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

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

        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )
