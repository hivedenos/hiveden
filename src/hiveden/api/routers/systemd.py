import traceback
import logging
from fastapi import APIRouter, HTTPException

from hiveden.api.dtos import (
    DataResponse, 
    SuccessResponse, 
    SystemdServiceListResponse, 
    SystemdServiceResponse
)
from hiveden.systemd.manager import SystemdManager
from hiveden.systemd.models import ServiceActionRequest

router = APIRouter(prefix="/systemd", tags=["Systemd"])
logger = logging.getLogger(__name__)

@router.get("/services", response_model=SystemdServiceListResponse)
def list_services():
    """List all managed systemd services."""
    logger.info("Listing systemd services")
    try:
        manager = SystemdManager()
        return SystemdServiceListResponse(data=manager.list_services())
    except Exception as e:
        logger.error(f"Error listing services: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/{service_name}", response_model=SystemdServiceResponse)
def get_service(service_name: str):
    """Get status of a specific service."""
    logger.info(f"Getting status for service: {service_name}")
    try:
        manager = SystemdManager()
        status = manager.get_service_status(service_name)
        if not status:
            raise HTTPException(status_code=404, detail="Service not found")
        return SystemdServiceResponse(data=status)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service {service_name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/services/{service_name}/{action}", response_model=SystemdServiceResponse)
def manage_service(service_name: str, action: str):
    """
    Perform action on service (start, stop, restart, enable, disable).
    Note: action parameter in path is for convenience/REST style, 
    but we can also use body. Using path here as per request.
    """
    logger.info(f"Managing service {service_name}: action={action}")
    try:
        manager = SystemdManager()
        status = manager.manage_service(service_name, action)
        return SystemdServiceResponse(data=status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error managing service {service_name}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

