import pytest
from unittest.mock import patch, MagicMock

def test_backup_validation_failure():
    from hiveden.backups.manager import BackupManager
    
    # Mock config to have no backup directory
    with patch("hiveden.config.settings.config.backup_directory", None):
        manager = BackupManager()
        # Should raise ValueError because config is missing and no arg provided
        with pytest.raises(ValueError, match="Backup configuration missing"):
            manager.validate_config()

def test_backup_validation_success(tmp_path):
    from hiveden.backups.manager import BackupManager
    
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    
    with patch("hiveden.config.settings.config.backup_directory", str(backup_dir)):
        manager = BackupManager()
        # Should pass
        manager.validate_config()
        assert manager.get_backup_directory() == str(backup_dir)

def test_backup_creation_uses_config(tmp_path):
    from hiveden.backups.manager import BackupManager
    
    backup_dir = tmp_path / "default_backups"
    
    with patch("hiveden.config.settings.config.backup_directory", str(backup_dir)):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            
            manager = BackupManager()
            # Call without explicit output_dir
            manager.create_postgres_backup("mydb")
            
            # Verify it used the config directory
            args = mock_run.call_args[0][0]
            assert str(backup_dir) in args[2] # filepath is likely the 3rd arg: pg_dump -f filepath dbname
