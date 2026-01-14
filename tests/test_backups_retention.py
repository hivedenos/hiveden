import pytest
from unittest.mock import patch, MagicMock
import os
import time
import sys

# Mock the DockerManager module BEFORE importing BackupManager
mock_docker_module = MagicMock()
sys.modules["hiveden.docker.containers"] = mock_docker_module

def test_list_backups(tmp_path):
    from hiveden.backups.manager import BackupManager
    
    manager = BackupManager()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    
    # Create dummy backup files
    (backup_dir / "db1_20230101_120000.sql").touch()
    (backup_dir / "db2_20230101_120000.sql").touch()
    (backup_dir / "hiveden_app_data_20230101_120000.tar.gz").touch()
    
    with patch("hiveden.config.settings.config.backup_directory", str(backup_dir)):
        # Test list all
        all_backups = manager.list_backups()
        assert len(all_backups) == 3
        
        # Test filter by type: database
        db_backups = manager.list_backups(backup_type="database")
        assert len(db_backups) == 2
        assert all(b['type'] == 'database' for b in db_backups)
        
        # Test filter by type: application
        app_backups = manager.list_backups(backup_type="application")
        assert len(app_backups) == 1
        assert app_backups[0]['type'] == 'application'
        
        # Test filter by target
        db1_backups = manager.list_backups(target="db1")
        assert len(db1_backups) == 1
        assert db1_backups[0]['target'] == 'db1'

def test_enforce_retention_policy(tmp_path):
    from hiveden.backups.manager import BackupManager
    
    manager = BackupManager()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    
    # Create 5 files with different mtimes
    files = []
    for i in range(5):
        p = backup_dir / f"db_2023010{i+1}_120000.sql"
        p.touch()
        # Set mtime to ensure order (though name sort might be used, mtime is safer)
        os.utime(p, (time.time() + i*10, time.time() + i*10))
        files.append(p)
        
    with patch("hiveden.config.settings.config.backup_directory", str(backup_dir)):
        # Keep 3, should delete oldest 2 (files[0] and files[1])
        manager.enforce_retention_policy(target="db", backup_type="database", max_backups=3)
        
        remaining = sorted(list(backup_dir.glob("*.sql")))
        assert len(remaining) == 3
        assert files[0].name not in [p.name for p in remaining]
        assert files[1].name not in [p.name for p in remaining]
        assert files[4].name in [p.name for p in remaining]

def test_backup_creation_enforces_retention(tmp_path):
    from hiveden.backups.manager import BackupManager
    
    manager = BackupManager()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    
    # Create existing backups for 'mydb'
    for i in range(5):
        (backup_dir / f"mydb_2023010{i}_120000.sql").touch()
        
    with patch("hiveden.config.settings.config.backup_directory", str(backup_dir)):
        with patch("hiveden.backups.manager.BackupManager.get_retention_count", return_value=3):
            with patch("subprocess.run"): # Mock pg_dump
                manager.create_postgres_backup("mydb")
                
    # Result should be 3.
    remaining = list(backup_dir.glob("mydb_*.sql"))
    assert len(remaining) == 3
