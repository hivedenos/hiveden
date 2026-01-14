from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from hiveden.backups.manager import BackupManager
from hiveden.backups.scheduler import BackupScheduler

router = APIRouter(prefix="/backups", tags=["backups"])

class Backup(BaseModel):
    path: str
    filename: str
    type: str
    target: str
    timestamp: str
    size: int
    mtime: float

class BackupCreateRequest(BaseModel):
    type: str # 'database' or 'application'
    target: str # db_name or app name (used for filename/retention)
    source_dirs: Optional[List[str]] = None
    container_name: Optional[str] = None

class BackupRestoreRequest(BaseModel):
    backup_file: str
    target: str # db_name or dest_dir
    type: str # 'database' or 'application'

class BackupConfig(BaseModel):
    directory: str
    retention_count: int

class BackupSchedule(BaseModel):
    id: Optional[str] = None
    cron: str
    type: str
    target: str
    container_name: Optional[str] = None
    source_dirs: Optional[List[str]] = None

@router.get("/config", response_model=BackupConfig)
def get_backup_config():
    from hiveden.db.session import get_db_manager
    from hiveden.db.repositories.core import ConfigRepository, ModuleRepository
    from hiveden.config.settings import config as app_config
    
    db_manager = get_db_manager()
    config_repo = ConfigRepository(db_manager)
    module_repo = ModuleRepository(db_manager)
    
    # Defaults
    directory = app_config.backup_directory
    retention_count = 5 
    
    try:
        core = module_repo.get_by_short_name('core')
        if core:
            db_dir = config_repo.get_by_module_and_key(core.id, 'backups.directory')
            if db_dir:
                directory = db_dir['value']
            
            db_ret = config_repo.get_by_module_and_key(core.id, 'backups.retention_count')
            if db_ret:
                retention_count = int(db_ret['value'])
    except Exception:
        pass
        
    return BackupConfig(directory=directory or "", retention_count=retention_count)

@router.put("/config", response_model=BackupConfig)
def update_backup_config(config: BackupConfig):
    from hiveden.db.session import get_db_manager
    from hiveden.db.repositories.core import ConfigRepository
    
    db_manager = get_db_manager()
    config_repo = ConfigRepository(db_manager)
    
    try:
        config_repo.set_value('core', 'backups.directory', config.directory)
        config_repo.set_value('core', 'backups.retention_count', str(config.retention_count))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")
        
    return config

@router.get("/schedules", response_model=List[BackupSchedule])
def list_schedules():
    scheduler = BackupScheduler()
    return scheduler.get_schedules()

@router.post("/schedules", response_model=BackupSchedule)
def create_schedule(schedule: BackupSchedule):
    scheduler = BackupScheduler()
    try:
        data = schedule.dict()
        new_schedule = scheduler.add_schedule(data)
        return new_schedule
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {e}")

@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: str):
    scheduler = BackupScheduler()
    try:
        scheduler.delete_schedule(schedule_id)
        return {"message": "Schedule deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {e}")

@router.get("", response_model=List[Backup])
def list_backups(
    type: Optional[str] = Query(None),
    target: Optional[str] = Query(None)
):
    manager = BackupManager()
    return manager.list_backups(backup_type=type, target=target)

@router.post("", status_code=201)
def create_backup(request: BackupCreateRequest):
    manager = BackupManager()
    try:
        path = None
        if request.type == "database":
            path = manager.create_postgres_backup(db_name=request.target)
        elif request.type == "application":
            if not request.source_dirs:
                raise HTTPException(status_code=400, detail="source_dirs required for application backup")
            path = manager.create_app_data_backup(
                source_dirs=request.source_dirs,
                container_name=request.container_name
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid backup type. Must be 'database' or 'application'.")
        
        return {"path": path, "message": "Backup created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/restore")
def restore_backup(request: BackupRestoreRequest):
    manager = BackupManager()
    try:
        if request.type == "database":
            manager.restore_postgres_backup(backup_file=request.backup_file, db_name=request.target)
        elif request.type == "application":
            manager.restore_app_data_backup(backup_file=request.backup_file, dest_dir=request.target)
        else:
             raise HTTPException(status_code=400, detail="Invalid backup type")
        
        return {"message": "Restore completed successfully"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
