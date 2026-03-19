from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiveden.api.routers import explorer as explorer_router
from hiveden.explorer.models import ExplorerOperation, OperationStatus
from hiveden.explorer.operations import ExplorerService


class _FakeManager:
    def __init__(self):
        self.operations = {}
        self.counter = 0

    def create_operation(self, op_type, status):
        self.counter += 1
        op = ExplorerOperation(
            id=f"op-{self.counter}",
            operation_type=op_type,
            status=status,
        )
        self.operations[op.id] = op.model_copy(deep=True)
        return op

    def update_operation(self, op):
        self.operations[op.id] = op.model_copy(deep=True)

    def get_operation(self, op_id):
        op = self.operations.get(op_id)
        return op.model_copy(deep=True) if op else None

    def get_operations(self, limit=50, offset=0):
        values = list(self.operations.values())
        return [op.model_copy(deep=True) for op in values[offset : offset + limit]]


def _build_client(tmp_path):
    app = FastAPI()
    app.include_router(explorer_router.router)
    client = TestClient(app)
    manager = _FakeManager()

    original_get_service = explorer_router.get_service
    original_get_manager = explorer_router.get_manager
    explorer_router.get_service = lambda: ExplorerService(root_directory=str(tmp_path))
    explorer_router.get_manager = lambda: manager

    return client, manager, original_get_service, original_get_manager


def _restore_dependencies(original_get_service, original_get_manager):
    explorer_router.get_service = original_get_service
    explorer_router.get_manager = original_get_manager


def test_prepare_upload_creates_pending_operation_with_conflicts(tmp_path):
    target_dir = tmp_path / "uploads"
    target_dir.mkdir()
    (target_dir / "exists.txt").write_text("old")

    client, _manager, original_get_service, original_get_manager = _build_client(
        tmp_path
    )
    try:
        response = client.post(
            "/explorer/upload/prepare",
            json={
                "destination": str(target_dir),
                "files": [
                    {"name": "exists.txt", "size": 3},
                    {"name": "fresh.txt", "size": 5},
                ],
            },
        )
    finally:
        _restore_dependencies(original_get_service, original_get_manager)

    assert response.status_code == 201
    body = response.json()
    assert body["operation_id"] == "op-1"
    assert body["operation"]["status"] == OperationStatus.PENDING
    assert body["files"][0]["result"]["conflict"] is True
    assert body["files"][1]["result"]["conflict"] is False


def test_check_upload_conflicts_does_not_create_operation(tmp_path):
    target_dir = tmp_path / "uploads"
    target_dir.mkdir()
    (target_dir / "exists.txt").write_text("old")

    client, manager, original_get_service, original_get_manager = _build_client(
        tmp_path
    )
    try:
        response = client.post(
            "/explorer/upload/conflicts",
            json={
                "destination": str(target_dir),
                "files": [{"name": "exists.txt", "size": 3}],
            },
        )
    finally:
        _restore_dependencies(original_get_service, original_get_manager)

    assert response.status_code == 200
    assert response.json()["files"][0]["result"]["conflict"] is True
    assert manager.get_operations() == []


def test_upload_file_to_destination_directory_tracks_operation(tmp_path):
    target_dir = tmp_path / "uploads"
    target_dir.mkdir()

    client, manager, original_get_service, original_get_manager = _build_client(
        tmp_path
    )
    try:
        response = client.post(
            "/explorer/upload",
            data={"destination": str(target_dir)},
            files=[("files", ("hello.txt", b"hello world", "text/plain"))],
        )
    finally:
        _restore_dependencies(original_get_service, original_get_manager)

    assert response.status_code == 201
    body = response.json()
    assert body["operation_id"] == "op-1"
    assert body["destination"] == str(target_dir)
    assert body["uploaded"][0]["name"] == "hello.txt"
    assert body["operation"]["status"] == OperationStatus.COMPLETED
    assert body["operation"]["result"]["files"][0]["progress"] == 100
    assert body["operation"]["result"]["summary"]["completed"] == 1
    assert body["operation"]["result"]["summary"]["created"] == 1
    assert body["operation"]["result"]["uploaded_bytes"] == len(b"hello world")
    assert (
        body["operation"]["result"]["files"][0]["status"] == OperationStatus.COMPLETED
    )
    operation = manager.get_operation("op-1")
    assert operation is not None
    assert operation.result["files"][0]["uploaded_bytes"] == len(b"hello world")
    assert (target_dir / "hello.txt").read_text() == "hello world"


def test_upload_reports_partial_success_and_operation_progress(tmp_path):
    target_dir = tmp_path / "uploads"
    target_dir.mkdir()
    existing = target_dir / "hello.txt"
    existing.write_text("old")

    client, manager, original_get_service, original_get_manager = _build_client(
        tmp_path
    )
    try:
        response = client.post(
            "/explorer/upload",
            data={"destination": str(target_dir)},
            files=[
                ("files", ("hello.txt", b"new", "text/plain")),
                ("files", ("fresh.txt", b"fresh", "text/plain")),
            ],
        )
        operation_response = client.get("/explorer/operations/op-1")
        operations_list = client.get("/explorer/operations")
    finally:
        _restore_dependencies(original_get_service, original_get_manager)

    assert response.status_code == 207
    body = response.json()
    assert body["operation_id"] == "op-1"
    assert body["operation"]["status"] == OperationStatus.COMPLETED
    assert body["operation"]["processed_items"] == 2
    assert len(body["operation"]["result"]["files"]) == 2
    assert body["operation"]["result"]["summary"]["skipped"] == 1
    assert body["operation"]["result"]["summary"]["completed"] == 1
    assert body["operation"]["result"]["summary"]["created"] == 1
    assert body["operation"]["result"]["files"][0]["status"] == "skipped"
    assert (
        body["operation"]["result"]["files"][1]["status"] == OperationStatus.COMPLETED
    )
    assert body["uploaded"][0]["name"] == "fresh.txt"
    assert existing.read_text() == "old"
    assert (target_dir / "fresh.txt").read_text() == "fresh"

    assert operation_response.status_code == 200
    assert (
        operation_response.json()["operation"]["result"]["files"][0]["status"]
        == "skipped"
    )

    assert operations_list.status_code == 200
    assert (
        operations_list.json()["operations"][0]["result"]["files"][1]["name"]
        == "fresh.txt"
    )


def test_cancel_upload_operation_blocks_later_upload(tmp_path):
    target_dir = tmp_path / "uploads"
    target_dir.mkdir()

    client, _manager, original_get_service, original_get_manager = _build_client(
        tmp_path
    )
    try:
        prepare = client.post(
            "/explorer/upload/prepare",
            json={
                "destination": str(target_dir),
                "files": [{"name": "later.txt", "size": 5}],
            },
        )
        operation_id = prepare.json()["operation_id"]
        cancel = client.post(f"/explorer/operations/{operation_id}/cancel")
        upload = client.post(
            "/explorer/upload",
            data={"destination": str(target_dir), "operation_id": operation_id},
            files=[("files", ("later.txt", b"later", "text/plain"))],
        )
    finally:
        _restore_dependencies(original_get_service, original_get_manager)

    assert cancel.status_code == 200
    assert cancel.json()["operation"]["status"] == OperationStatus.CANCELLED
    assert upload.status_code == 409
    assert not (target_dir / "later.txt").exists()
