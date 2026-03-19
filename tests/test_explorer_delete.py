from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiveden.api.routers import explorer as explorer_router
from hiveden.explorer.operations import ExplorerService


def test_delete_directory_is_recursive_by_default(tmp_path):
    target_dir = tmp_path / "parent"
    target_dir.mkdir()
    (target_dir / "child.txt").write_text("content")

    app = FastAPI()
    app.include_router(explorer_router.router)
    client = TestClient(app)

    original_get_service = explorer_router.get_service
    explorer_router.get_service = lambda: ExplorerService(root_directory=str(tmp_path))
    try:
        response = client.request(
            "DELETE",
            "/explorer/delete",
            json={"paths": [str(target_dir)]},
        )
    finally:
        explorer_router.get_service = original_get_service

    assert response.status_code == 200
    assert not target_dir.exists()
