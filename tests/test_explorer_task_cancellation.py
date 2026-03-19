from pathlib import Path

from hiveden.explorer.models import ExplorerOperation, OperationStatus
from hiveden.explorer.tasks import perform_paste, perform_search


class FakeManager:
    def __init__(self, operation: ExplorerOperation, cancel_on_update: int = 1):
        self.operation = operation
        self.cancel_on_update = cancel_on_update
        self.update_calls = 0

    def get_operation(self, _op_id):
        return self.operation

    def update_operation(self, op):
        self.update_calls += 1
        self.operation = op
        if (
            self.update_calls >= self.cancel_on_update
            and self.operation.status == OperationStatus.IN_PROGRESS
        ):
            self.operation.status = OperationStatus.CANCELLED


class FakeExplorerService:
    def get_file_entry(self, path):
        return type("Entry", (), {"dict": lambda self: {"path": path}})()


def test_search_task_stops_when_operation_cancelled(monkeypatch, tmp_path):
    for index in range(3):
        (tmp_path / f"file{index}.txt").write_text("data")

    operation = ExplorerOperation(
        id="search-1",
        operation_type="search",
        status=OperationStatus.PENDING,
    )
    manager = FakeManager(operation)

    monkeypatch.setattr("hiveden.explorer.tasks.ExplorerManager", lambda: manager)
    monkeypatch.setattr(
        "hiveden.explorer.tasks.ExplorerService", lambda: FakeExplorerService()
    )

    perform_search("search-1", str(tmp_path), "file", False, True, "file", True)

    assert manager.operation.status == OperationStatus.CANCELLED
    assert manager.operation.error_message == "Operation cancelled"


def test_paste_task_stops_when_operation_cancelled(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("content")
    destination = tmp_path / "dest"
    destination.mkdir()

    operation = ExplorerOperation(
        id="paste-1",
        operation_type="copy",
        status=OperationStatus.PENDING,
    )
    manager = FakeManager(operation)

    monkeypatch.setattr("hiveden.explorer.tasks.ExplorerManager", lambda: manager)

    perform_paste("paste-1", [str(source)], str(destination), "rename", "{name} ({n})")

    assert manager.operation.status == OperationStatus.CANCELLED
    assert manager.operation.error_message == "Operation cancelled"
    assert not (destination / source.name).exists()
