import os.path
from typing import Optional, List
from hiveden.db.repositories.base import BaseRepository
from hiveden.explorer.models import FilesystemLocation

class LocationRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'filesystem_locations', model_class=FilesystemLocation)

    def get_by_key(self, key: str) -> Optional[FilesystemLocation]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM filesystem_locations WHERE key = %s"
            cursor.execute(query, (key,))
            row = cursor.fetchone()
            if not row:
                return None
            
            # Use same mapping as ExplorerManager for consistency
            return FilesystemLocation(
                id=row['id'],
                key=row['key'],
                label=row['label'],
                name=row['label'], # Compatibility alias
                path=row['path'],
                type=row['type'],
                description=row['description'],
                is_editable=row['is_editable'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        finally:
            conn.close()

    def get_system_locations(self) -> List[FilesystemLocation]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM filesystem_locations WHERE type = 'system_root'"
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                FilesystemLocation(
                    id=row['id'],
                    key=row['key'],
                    label=row['label'],
                    name=row['label'],
                    path=row['path'],
                    type=row['type'],
                    description=row['description'],
                    is_editable=row['is_editable'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    exists=(os.path.exists(row['path']) and os.path.isdir(row['path']) and not row['path'].startswith("/hiveden-temp-root"))
                ) for row in rows
            ]
        finally:
            conn.close()
