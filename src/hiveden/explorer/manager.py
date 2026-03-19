import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from hiveden.db.session import get_db_manager
from hiveden.explorer.models import (
    ExplorerConfig,
    ExplorerOperation,
    FilesystemLocation,
    OperationStatus,
)


class ExplorerManager:
    def __init__(self):
        self.db = get_db_manager()

    @staticmethod
    def _parse_datetime(value: Optional[datetime]) -> Optional[datetime]:
        if isinstance(value, datetime) or value is None:
            return value
        return datetime.fromisoformat(value)

    def _build_location(self, row: Dict[str, Any]) -> FilesystemLocation:
        return FilesystemLocation(
            id=row["id"],
            key=row["key"],
            label=row["label"],
            name=row["label"],
            path=row["path"],
            type=row["type"],
            description=row["description"],
            is_editable=row["is_editable"],
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )

    def _build_operation(self, row: Dict[str, Any]) -> ExplorerOperation:
        source_paths = row["source_paths"]
        if isinstance(source_paths, str):
            try:
                source_paths = json.loads(source_paths)
            except (TypeError, ValueError):
                pass

        result = row["result"]
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (TypeError, ValueError):
                pass

        return ExplorerOperation(
            id=row["id"],
            operation_type=row["operation_type"],
            status=row["status"],
            progress=row["progress"],
            total_items=row["total_items"],
            processed_items=row["processed_items"],
            source_paths=source_paths,
            destination_path=row["destination_path"],
            error_message=row["error_message"],
            result=result,
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
            completed_at=self._parse_datetime(row["completed_at"]),
        )

    def get_config(self) -> Dict[str, str]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM explorer_config")
            rows = cursor.fetchall()
            config = {
                "show_hidden_files": "false",
                "usb_mount_path": "/media",
                "root_directory": "/",
            }
            for row in rows:
                row_data = cast(Dict[str, Any], row)
                config[row_data["key"]] = row_data["value"]
            return config
        finally:
            conn.close()

    def update_config(self, key: str, value: str):
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM explorer_config WHERE key = %s", (key,))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE explorer_config SET value = %s, updated_at = CURRENT_TIMESTAMP WHERE key = %s",
                    (value, key),
                )
            else:
                cursor.execute(
                    "INSERT INTO explorer_config (key, value) VALUES (%s, %s)",
                    (key, value),
                )
            conn.commit()
        finally:
            conn.close()

    def get_locations(self) -> List[FilesystemLocation]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, key, label, path, type, description, is_editable, created_at, updated_at FROM filesystem_locations ORDER BY label"
            )
            rows = cursor.fetchall()
            return [self._build_location(cast(Dict[str, Any], row)) for row in rows]
        finally:
            conn.close()

    def create_location(
        self,
        label: str,
        path: str,
        type: str = "user_bookmark",
        description: Optional[str] = None,
    ) -> FilesystemLocation:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO filesystem_locations (label, path, type, description) VALUES (%s, %s, %s, %s) RETURNING id",
                (label, path, type, description),
            )
            row = cast(Dict[str, Any], cursor.fetchone())
            location_id = row["id"]
            conn.commit()
            location = self.get_location(location_id)
            if location is None:
                raise ValueError(f"Location {location_id} was not created")
            return location
        finally:
            conn.close()

    def update_location(
        self,
        location_id: int,
        label: Optional[str] = None,
        path: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[FilesystemLocation]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            updates = []
            params = []
            if label:
                updates.append("label = %s")
                params.append(label)
            if path:
                updates.append("path = %s")
                params.append(path)
            if description is not None:
                updates.append("description = %s")
                params.append(description)
            if not updates:
                return self.get_location(location_id)
            updates.append("updated_at = CURRENT_TIMESTAMP")
            query = (
                f"UPDATE filesystem_locations SET {', '.join(updates)} WHERE id = %s"
            )
            params.append(location_id)
            cursor.execute(query, tuple(params))
            conn.commit()
            return self.get_location(location_id)
        finally:
            conn.close()

    def get_location(self, location_id: int) -> Optional[FilesystemLocation]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, key, label, path, type, description, is_editable, created_at, updated_at FROM filesystem_locations WHERE id = %s",
                (location_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._build_location(cast(Dict[str, Any], row))
        finally:
            conn.close()

    def delete_location(self, location_id: int):
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_editable FROM filesystem_locations WHERE id = %s",
                (location_id,),
            )
            row = cursor.fetchone()
            if row and not cast(Dict[str, Any], row)["is_editable"]:
                raise ValueError("Cannot delete a system location")
            cursor.execute(
                "DELETE FROM filesystem_locations WHERE id = %s", (location_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def create_operation(
        self, op_type: str, status: str = OperationStatus.PENDING
    ) -> ExplorerOperation:
        op_id = str(uuid.uuid4())
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO explorer_operations (id, operation_type, status) VALUES (%s, %s, %s)",
                (op_id, op_type, status),
            )
            conn.commit()
            return ExplorerOperation(id=op_id, operation_type=op_type, status=status)
        finally:
            conn.close()

    def update_operation(self, op: ExplorerOperation):
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            def json_serial(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            source_paths_json = (
                json.dumps(op.source_paths, default=json_serial)
                if isinstance(op.source_paths, list)
                else op.source_paths
            )
            result_json = (
                json.dumps(op.result, default=json_serial)
                if isinstance(op.result, (dict, list))
                else op.result
            )
            cursor.execute(
                """
                UPDATE explorer_operations
                SET status = %s, progress = %s, total_items = %s, processed_items = %s,
                    source_paths = %s, destination_path = %s, error_message = %s, result = %s,
                    updated_at = CURRENT_TIMESTAMP, completed_at = %s
                WHERE id = %s
                """,
                (
                    op.status,
                    op.progress,
                    op.total_items,
                    op.processed_items,
                    source_paths_json,
                    op.destination_path,
                    op.error_message,
                    result_json,
                    op.completed_at,
                    op.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_operation(self, op_id: str) -> Optional[ExplorerOperation]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, operation_type, status, progress, total_items, processed_items, source_paths, destination_path, error_message, result, created_at, updated_at, completed_at FROM explorer_operations WHERE id = %s",
                (op_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._build_operation(cast(Dict[str, Any], row))
        finally:
            conn.close()

    def get_operations(
        self, limit: int = 50, offset: int = 0
    ) -> List[ExplorerOperation]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, operation_type, status, progress, total_items, processed_items, source_paths, destination_path, error_message, result, created_at, updated_at, completed_at FROM explorer_operations ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cursor.fetchall()
            return [self._build_operation(cast(Dict[str, Any], row)) for row in rows]
        finally:
            conn.close()

    def delete_operation(self, op_id: str):
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM explorer_operations WHERE id = %s", (op_id,))
            conn.commit()
        finally:
            conn.close()
