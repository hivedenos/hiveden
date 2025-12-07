from fastapi import APIRouter, HTTPException

from hiveden.api.dtos import DataResponse

router = APIRouter(prefix="/info", tags=["Info"])

@router.get("/os", response_model=DataResponse)
def get_os_info_endpoint():
    from hiveden.hwosinfo.os import get_os_info
    try:
        return DataResponse(data=get_os_info())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hw", response_model=DataResponse)
def get_hw_info_endpoint():
    from hiveden.hwosinfo.hw import get_hw_info
    try:
        return DataResponse(data=get_hw_info())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version", response_model=DataResponse)
def get_version_endpoint():
    from hiveden.version import get_version
    try:
        return DataResponse(data={"version": get_version()})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
