from fastapi import APIRouter, HTTPException
from fastapi.logger import logger
import traceback

from hiveden.api.dtos import DataResponse
from hiveden.hwosinfo.models import OSInfo, HWInfo

router = APIRouter(prefix="/info", tags=["Info"])

@router.get("/os", response_model=DataResponse)
def get_os_info_endpoint():
    from hiveden.hwosinfo.os import get_os_info
    try:
        return DataResponse(data=OSInfo(**get_os_info()))
    except Exception as e:
        logger.error(f"Error getting OS info: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hw", response_model=DataResponse)
def get_hw_info_endpoint():
    from hiveden.hwosinfo.hw import get_hw_info
    try:
        return DataResponse(data=HWInfo(**get_hw_info()))
    except Exception as e:
        logger.error(f"Error getting hardware info: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version", response_model=DataResponse)
def get_version_endpoint():
    from hiveden.version import get_version
    try:
        return DataResponse(data={"version": get_version()})
    except Exception as e:
        logger.error(f"Error getting version info: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
