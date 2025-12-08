from fastapi import APIRouter, HTTPException
from fastapi.logger import logger
import traceback

from hiveden.api.dtos import DataResponse, SuccessResponse, ZFSDatasetCreate, ZFSPoolCreate
from hiveden.shares.models import ZFSPool, ZFSDataset, BtrfsVolume, BtrfsShare

router = APIRouter(prefix="/shares", tags=["Shares"])

@router.get("/zfs/pools", response_model=DataResponse)
def list_zfs_pools_endpoint():
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        # Convert dicts to models
        pools = [ZFSPool(name=p['name']) for p in manager.list_pools()]
        return DataResponse(data=pools)
    except Exception as e:
        logger.error(f"Error listing ZFS pools: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zfs/pools", response_model=SuccessResponse)
def create_zfs_pool_endpoint(pool: ZFSPoolCreate):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.create_pool(pool.name, pool.devices)
        return SuccessResponse(message=f"Pool {pool.name} created.")
    except Exception as e:
        logger.error(f"Error creating ZFS pool: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/zfs/pools/{name}", response_model=SuccessResponse)
def destroy_zfs_pool_endpoint(name: str):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.destroy_pool(name)
        return SuccessResponse(message=f"Pool {name} destroyed.")
    except Exception as e:
        logger.error(f"Error destroying ZFS pool: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/zfs/datasets/{pool}", response_model=DataResponse)
def list_zfs_datasets_endpoint(pool: str):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        datasets = [ZFSDataset(name=d['name']) for d in manager.list_datasets(pool)]
        return DataResponse(data=datasets)
    except Exception as e:
        logger.error(f"Error listing ZFS datasets: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/zfs/datasets", response_model=SuccessResponse)
def create_zfs_dataset_endpoint(dataset: ZFSDatasetCreate):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.create_dataset(dataset.name)
        return SuccessResponse(message=f"Dataset {dataset.name} created.")
    except Exception as e:
        logger.error(f"Error creating ZFS dataset: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/zfs/datasets/{name}", response_model=SuccessResponse)
def destroy_zfs_dataset_endpoint(name: str):
    from hiveden.shares.zfs import ZFSManager
    try:
        manager = ZFSManager()
        manager.destroy_dataset(name)
        return SuccessResponse(message=f"Dataset {name} destroyed.")
    except Exception as e:
        logger.error(f"Error destroying ZFS dataset: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/zfs/available-devices", response_model=DataResponse)
def list_available_devices_endpoint():
    from hiveden.hwosinfo.hw import get_available_devices
    try:
        return DataResponse(data=get_available_devices())
    except Exception as e:
        logger.error(f"Error listing available ZFS devices: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

from hiveden.api.dtos import SMBShareCreate

@router.get("/smb", response_model=DataResponse)
def list_smb_shares_endpoint():
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        return DataResponse(data=manager.list_shares())
    except Exception as e:
        logger.error(f"Error creating SMB share: {e}\n{traceback.format_exc()}")
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
        logger.error(f"Error creating SMB share: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/smb/{name}", response_model=SuccessResponse)
def destroy_smb_share_endpoint(name: str):
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        manager.delete_share(name)
        return SuccessResponse(message=f"Share {name} deleted.")
    except Exception as e:
        logger.error(f"Error destroying SMB share: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


from hiveden.api.dtos import CreateBtrfsShareRequest

@router.get("/btrfs/volumes", response_model=DataResponse)
def list_btrfs_volumes_endpoint():
    from hiveden.shares.btrfs import BtrfsManager
    try:
        manager = BtrfsManager()
        # manager.list_volumes() returns List[BtrfsVolume]
        return DataResponse(data=manager.list_volumes())
    except Exception as e:
        logger.error(f"Error listing Btrfs volumes: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/btrfs/shares", response_model=DataResponse)
def list_btrfs_shares_endpoint():
    from hiveden.shares.btrfs import BtrfsManager
    try:
        manager = BtrfsManager()
        # manager.list_shares() returns List[BtrfsShare]
        return DataResponse(data=manager.list_shares())
    except Exception as e:
        logger.error(f"Error listing Btrfs shares: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/btrfs/shares", response_model=SuccessResponse)
def create_btrfs_share_endpoint(share: CreateBtrfsShareRequest):
    from hiveden.shares.btrfs import BtrfsManager
    try:
        manager = BtrfsManager()
        manager.create_share(
            parent_path=share.parent_path,
            name=share.name,
            mount_path=share.mount_path
        )
        return SuccessResponse(message=f"Btrfs share {share.name} created and mounted.")
    except ValueError as e:
        logger.error(f"Validation error creating Btrfs share: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating Btrfs share: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
