from unittest.mock import MagicMock, patch
import pytest
import sys

# Mock APScheduler modules
sys.modules["apscheduler.schedulers.asyncio"] = MagicMock()
sys.modules["apscheduler.triggers.cron"] = MagicMock()
# Mock dependencies of BackupManager
sys.modules["yoyo"] = MagicMock()
sys.modules["hiveden.docker.containers"] = MagicMock()

def test_scheduler_add_job():
    from hiveden.backups.scheduler import BackupScheduler
    
    with patch("hiveden.backups.scheduler.AsyncIOScheduler") as MockScheduler:
        with patch("hiveden.backups.scheduler.CronTrigger") as MockTrigger:
            mock_sched_instance = MockScheduler.return_value
            scheduler = BackupScheduler()
            
            # Test simple daily backup
            scheduler.schedule_backup(
                schedule_id="job1",
                cron_expression="0 2 * * *", # 2 AM
                backup_type="database",
                target="mydb"
            )
            
            MockTrigger.from_crontab.assert_called_with("0 2 * * *")
            mock_sched_instance.add_job.assert_called()
            call_kwargs = mock_sched_instance.add_job.call_args[1]
            assert call_kwargs['id'] == "job1"
            assert call_kwargs['replace_existing'] == True

def test_scheduler_load_jobs():
    from hiveden.backups.scheduler import BackupScheduler
    
    # Mock DB config loading
    with patch("hiveden.backups.scheduler.AsyncIOScheduler"):
        with patch("hiveden.backups.scheduler.BackupManager") as MockBM:
            scheduler = BackupScheduler()
            
            # Mock get_db_config return value
            schedules = [
                {"id": "1", "cron": "0 0 * * *", "type": "database", "target": "db1"}
            ]
            
            with patch.object(scheduler, '_get_schedules_from_db', return_value=schedules):
                with patch.object(scheduler, 'schedule_backup') as mock_schedule:
                    scheduler.load_jobs()
                    mock_schedule.assert_called_once_with(
                        schedule_id="1",
                        cron_expression="0 0 * * *",
                        backup_type="database",
                        target="db1",
                        container_name=None,
                        source_dirs=None
                    )