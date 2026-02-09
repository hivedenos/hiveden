import traceback

from fastapi import APIRouter, HTTPException
from fastapi.logger import logger
from fastapi.responses import JSONResponse

from hiveden.api.dtos import (
    BtrfsShareListResponse,
    BtrfsVolumeListResponse,
    CreateBtrfsShareRequest,
    DataResponse,
    ErrorResponse,
    MountSMBShareRequest,
    SMBListResponse,
    SMBMount,
    SMBShareCreate,
    SuccessResponse,
    ZFSDatasetCreate,
    ZFSPoolCreate,
)
from hiveden.services.logs import LogService
from hiveden.shares.models import ZFSDataset, ZFSPool

router = APIRouter(prefix="/shares", tags=["Shares"])

@router.post("/smb/mount", response_model=SuccessResponse)
def mount_smb_share_endpoint(request: MountSMBShareRequest):
    """
    Mount a remote SMB share.
    """
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        manager.mount_share(
            remote_path=request.remote_path,
            mount_point=request.mount_point,
            username=request.username or "no_username",
            password=request.password or "no_password",
            options=request.options or [],
            persist=request.persist
        )

        LogService().info(
            actor="user",
            action="smb.mount",
            message=f"Mounted SMB share {request.remote_path} at {request.mount_point}",
            module="shares",
            metadata={"remote": request.remote_path, "mount": request.mount_point}
        )

        return SuccessResponse(message=f"Mounted {request.remote_path} at {request.mount_point}")
    except Exception as e:
        logger.error(f"Error mounting SMB share: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

@router.delete("/smb/mount", response_model=SuccessResponse)
def unmount_smb_share_endpoint(
    mount_point: str,
    remove_persistence: bool = False,
    force: bool = False
):
    """
    Unmount a remote SMB share.
    """
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        manager.unmount_share(
            mount_point=mount_point,
            remove_persistence=remove_persistence,
            force=force
        )

        LogService().info(
            actor="user",
            action="smb.unmount",
            message=f"Unmounted SMB share {mount_point}",
            module="shares",
            metadata={"mount": mount_point}
        )

        return SuccessResponse(message=f"Unmounted {mount_point}")
    except Exception as e:
        logger.error(f"Error unmounting SMB share: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

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

        LogService().info(
            actor="user",
            action="zfs.pool.create",
            message=f"Created ZFS pool {pool.name}",
            module="shares",
            metadata={"pool": pool.name, "devices": pool.devices}
        )

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

        LogService().info(
            actor="user",
            action="zfs.pool.destroy",
            message=f"Destroyed ZFS pool {name}",
            module="shares",
            metadata={"pool": name}
        )

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

        LogService().info(
            actor="user",
            action="zfs.dataset.create",
            message=f"Created ZFS dataset {dataset.name}",
            module="shares",
            metadata={"dataset": dataset.name}
        )

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

        LogService().info(
            actor="user",
            action="zfs.dataset.destroy",
            message=f"Destroyed ZFS dataset {name}",
            module="shares",
            metadata={"dataset": name}
        )

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

@router.get("/smb", response_model=SMBListResponse)
def list_smb_shares_endpoint():
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()

        exported = manager.list_shares()
        mounted_data = manager.list_mounted_shares()

        mounted = [SMBMount(**m) for m in mounted_data]

        return SMBListResponse(exported=exported, mounted=mounted)
    except Exception as e:
        logger.error(f"Error creating SMB share: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

@router.post("/smb", response_model=SuccessResponse)
def create_smb_share_endpoint(share: SMBShareCreate):
    from hiveden.shares.smb import SMBManager
    try:
        manager = SMBManager()
        manager.create_share(
            name=share.name,
            path=share.path,
            comment=share.comment or "",
            readonly=share.read_only,
            browsable=share.browsable,
            guest_ok=share.guest_ok
        )

        LogService().info(
            actor="user",
            action="smb.create",
            message=f"Created SMB share {share.name}",
            module="shares",
            metadata={"name": share.name, "path": share.path}
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

        LogService().info(
            actor="user",
            action="smb.delete",
            message=f"Deleted SMB share {name}",
            module="shares",
            metadata={"name": name}
        )

        return SuccessResponse(message=f"Share {name} deleted.")
    except Exception as e:
        logger.error(f"Error destroying SMB share: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/btrfs/volumes", response_model=BtrfsVolumeListResponse)
def list_btrfs_volumes_endpoint():
    from hiveden.shares.btrfs import BtrfsManager
    try:
        manager = BtrfsManager()
        # manager.list_volumes() returns List[BtrfsVolume]
        return BtrfsVolumeListResponse(data=manager.list_volumes())
    except Exception as e:
        logger.error(f"Error listing Btrfs volumes: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/btrfs/shares", response_model=BtrfsShareListResponse)
def list_btrfs_shares_endpoint():
    from hiveden.shares.btrfs import BtrfsManager
    try:
        manager = BtrfsManager()
        # manager.list_shares() returns List[BtrfsShare]
        return BtrfsShareListResponse(data=manager.list_shares())
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

        LogService().info(
            actor="user",
            action="btrfs.share.create",
            message=f"Created BTRFS share {share.name}",
            module="shares",
            metadata={"name": share.name, "parent": share.parent_path, "mount": share.mount_path}
        )

        return SuccessResponse(message=f"Btrfs share {share.name} created and mounted.")
    except ValueError as e:
        logger.error(f"Validation error creating Btrfs share: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating Btrfs share: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
