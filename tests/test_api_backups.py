from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest
import sys

# Mock yoyo to avoid dependency issues during import
sys.modules["yoyo"] = MagicMock()
# Mock apscheduler
sys.modules["apscheduler"] = MagicMock()
sys.modules["apscheduler.schedulers"] = MagicMock()
sys.modules["apscheduler.schedulers.asyncio"] = MagicMock()
sys.modules["apscheduler.triggers"] = MagicMock()
sys.modules["apscheduler.triggers.cron"] = MagicMock()

def test_router_registered():
    from hiveden.api.server import app
    
    with TestClient(app) as client:
        with patch("hiveden.api.routers.backups.BackupManager") as MockBM:
            MockBM.return_value.list_backups.return_value = []
            response = client.get("/backups")
            assert response.status_code != 404

def test_list_backups():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.api.routers.backups.BackupManager") as MockBM:
        mock_bm = MockBM.return_value
        mock_bm.list_backups.return_value = [
            {"filename": "test.sql", "type": "database", "target": "db", "size": 100, "mtime": 12345, "path": "/tmp/test.sql", "timestamp": "20230101_120000"}
        ]
        
        response = client.get("/backups")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["filename"] == "test.sql"
        
        client.get("/backups?type=database&target=db")
        mock_bm.list_backups.assert_called_with(backup_type="database", target="db")

def test_create_backup_postgres():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.api.routers.backups.BackupManager") as MockBM:
        mock_bm = MockBM.return_value
        mock_bm.create_postgres_backup.return_value = "/tmp/backup.sql"
        
        payload = {"type": "database", "target": "mydb"}
        response = client.post("/backups", json=payload)
        
        assert response.status_code == 201
        assert response.json()["path"] == "/tmp/backup.sql"
        mock_bm.create_postgres_backup.assert_called_with(db_name="mydb")

def test_create_backup_app():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.api.routers.backups.BackupManager") as MockBM:
        mock_bm = MockBM.return_value
        mock_bm.create_app_data_backup.return_value = "/tmp/backup.tar.gz"
        
        payload = {"type": "application", "target": "hiveden", "source_dirs": ["/data"], "container_name": "hiveden"}
        response = client.post("/backups", json=payload)
        
        assert response.status_code == 201
        mock_bm.create_app_data_backup.assert_called_with(source_dirs=["/data"], container_name="hiveden")

def test_get_config():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.db.session.get_db_manager"):
        with patch("hiveden.db.repositories.core.ConfigRepository") as MockConfigRepo:
            mock_repo = MockConfigRepo.return_value
            mock_repo.get_by_module_and_key.side_effect = [
                {"value": "/db/backups"}, # backups.directory
                {"value": "10"}           # backups.retention_count
            ]
            
            with patch("hiveden.db.repositories.core.ModuleRepository") as MockModuleRepo:
                mock_mod_repo = MockModuleRepo.return_value
                mock_mod_repo.get_by_short_name.return_value = MagicMock(id=1)
                
                response = client.get("/backups/config")
                assert response.status_code == 200
                data = response.json()
                assert data["directory"] == "/db/backups"
                assert data["retention_count"] == 10

def test_update_config():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.db.session.get_db_manager"):
        with patch("hiveden.db.repositories.core.ConfigRepository") as MockConfigRepo:
            mock_repo = MockConfigRepo.return_value
            
            payload = {"directory": "/new/backups", "retention_count": 7}
            response = client.put("/backups/config", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert data["directory"] == "/new/backups"
            assert data["retention_count"] == 7
            
            calls = mock_repo.set_value.call_args_list
            assert len(calls) == 2

def test_list_schedules():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.api.routers.backups.BackupScheduler") as MockScheduler:
        mock_instance = MockScheduler.return_value
        mock_instance.get_schedules.return_value = [
            {"id": "1", "cron": "0 0 * * *", "type": "database", "target": "db"}
        ]
        
        response = client.get("/backups/schedules")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "1"

def test_create_schedule():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.api.routers.backups.BackupScheduler") as MockScheduler:
        mock_instance = MockScheduler.return_value
        mock_instance.add_schedule.return_value = {
            "id": "new", 
            "cron": "0 0 * * *",
            "type": "database",
            "target": "db"
        }
        
        payload = {"cron": "0 0 * * *", "type": "database", "target": "db"}
        response = client.post("/backups/schedules", json=payload)
        
        assert response.status_code == 200
        assert response.json()["id"] == "new"
        mock_instance.add_schedule.assert_called_once()

def test_delete_schedule():
    from hiveden.api.routers.backups import router
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    with patch("hiveden.api.routers.backups.BackupScheduler") as MockScheduler:
        mock_instance = MockScheduler.return_value
        
        response = client.delete("/backups/schedules/123")
        
        assert response.status_code == 200
        mock_instance.delete_schedule.assert_called_with("123")
