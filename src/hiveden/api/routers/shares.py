from fastapi import APIRouter, HTTPException

from hiveden.api.dtos import DataResponse, SuccessResponse, ZFSDatasetCreate, ZFSPoolCreate

router = APIRouter(prefix="/shares", tags=["Shares"])

@router.get("/zfs/pools", response_model=DataResponse)
def list_zfs_pools_endpoint():
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        return DataResponse(data=manager.list_pools())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/zfs/pools", response_model=SuccessResponse)
def create_zfs_pool_endpoint(pool: ZFSPoolCreate):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.create_pool(pool.name, pool.devices)
        return SuccessResponse(message=f"Pool {pool.name} created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/zfs/pools/{name}", response_model=SuccessResponse)
def destroy_zfs_pool_endpoint(name: str):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.destroy_pool(name)
        return SuccessResponse(message=f"Pool {name} destroyed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/zfs/datasets/{pool}", response_model=DataResponse)
def list_zfs_datasets_endpoint(pool: str):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        return DataResponse(data=manager.list_datasets(pool))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/zfs/datasets", response_model=SuccessResponse)
def create_zfs_dataset_endpoint(dataset: ZFSDatasetCreate):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.create_dataset(dataset.name)
        return SuccessResponse(message=f"Dataset {dataset.name} created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/zfs/datasets/{name}", response_model=SuccessResponse)
def destroy_zfs_dataset_endpoint(name: str):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.destroy_dataset(name)
        return SuccessResponse(message=f"Dataset {name} destroyed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/zfs/available-devices", response_model=DataResponse)
def list_available_devices_endpoint():
    from hiveden.hwosinfo.hw import get_available_devices
    try:
        return DataResponse(data=get_available_devices())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from hiveden.api.dtos import SMBShareCreate

@router.get("/smb", response_model=DataResponse)
def list_smb_shares_endpoint():
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        return DataResponse(data=manager.list_shares())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/smb", response_model=SuccessResponse)
def create_smb_share_endpoint(share: SMBShareCreate):
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        manager.create_share(
            name=share.name,
            path=share.path,
            comment=share.comment,
            readonly=share.read_only,
            browsable=share.browsable,
            guest_ok=share.guest_ok
        )
        return SuccessResponse(message=f"Share {share.name} created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/smb/{name}", response_model=SuccessResponse)
def destroy_smb_share_endpoint(name: str):
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        manager.delete_share(name)
        return SuccessResponse(message=f"Share {name} deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
