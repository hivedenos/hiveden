from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from hiveden.backups.manager import BackupManager
import json
import logging
import uuid

logger = logging.getLogger(__name__)

class BackupScheduler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackupScheduler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.scheduler = AsyncIOScheduler()
        self.manager = BackupManager()
        self._initialized = True

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
        self.load_jobs()

    def _get_db_access(self):
        from hiveden.db.session import get_db_manager
        from hiveden.db.repositories.core import ConfigRepository, ModuleRepository
        
        db_manager = get_db_manager()
        module_repo = ModuleRepository(db_manager)
        config_repo = ConfigRepository(db_manager)
        core_module = module_repo.get_by_short_name('core')
        
        return config_repo, core_module

    def get_schedules(self):
        try:
            config_repo, core_module = self._get_db_access()
            if core_module:
                cfg = config_repo.get_by_module_and_key(core_module.id, 'backups.schedules')
                if cfg and cfg['value']:
                    return json.loads(cfg['value'])
        except Exception as e:
            logger.error(f"Failed to load schedules: {e}")
        return []

    def save_schedules(self, schedules):
        try:
            config_repo, core_module = self._get_db_access()
            if core_module:
                config_repo.set_value('core', 'backups.schedules', json.dumps(schedules))
                self.load_jobs() # Reload to apply changes
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")
            raise

    def add_schedule(self, schedule_data):
        schedules = self.get_schedules()
        if not schedule_data.get('id'):
            schedule_data['id'] = str(uuid.uuid4())
        
        schedules.append(schedule_data)
        self.save_schedules(schedules)
        return schedule_data

    def delete_schedule(self, schedule_id):
        schedules = self.get_schedules()
        schedules = [s for s in schedules if s['id'] != schedule_id]
        self.save_schedules(schedules)
        # Also remove from running scheduler
        try:
            self.scheduler.remove_job(schedule_id)
        except Exception:
            pass

    def load_jobs(self):
        # Clear existing jobs first? 
        # Or replace_existing=True in add_job handles it?
        # If we deleted a job in DB, we should remove it from scheduler.
        # Simplest is remove all and re-add.
        self.scheduler.remove_all_jobs()
        
        schedules = self.get_schedules()
        for s in schedules:
            try:
                self.schedule_backup(
                    schedule_id=s['id'],
                    cron_expression=s['cron'],
                    backup_type=s['type'],
                    target=s['target'],
                    container_name=s.get('container_name'),
                    source_dirs=s.get('source_dirs')
                )
            except Exception as e:
                logger.error(f"Failed to schedule job {s}: {e}")

    def schedule_backup(self, schedule_id, cron_expression, backup_type, target, container_name=None, source_dirs=None):
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
        except ValueError as e:
            logger.error(f"Invalid cron expression '{cron_expression}': {e}")
            return
        
        func = None
        kwargs = {}
        
        if backup_type == "database":
            func = self.manager.create_postgres_backup
            kwargs = {"db_name": target}
        elif backup_type == "application":
            func = self.manager.create_app_data_backup
            kwargs = {
                "source_dirs": source_dirs or [],
                "container_name": container_name
            }
            
        if func:
            self.scheduler.add_job(
                func,
                trigger=trigger,
                kwargs=kwargs,
                id=schedule_id,
                replace_existing=True,
                name=f"Backup {target}"
            )