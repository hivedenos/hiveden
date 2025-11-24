from typing import Optional, Dict, Any, Union
from hiveden.db.repositories.base import BaseRepository
from hiveden.db.models.module import Module

class ModuleRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'modules', model_class=Module)

    def get_by_name(self, name: str) -> Optional[Module]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM modules WHERE name = %s" if self.manager.db_type != 'sqlite' else "SELECT * FROM modules WHERE name = ?"
            cursor.execute(query, (name,))
            row = cursor.fetchone()
            return self._to_model(dict(row)) if row else None
        finally:
            conn.close()

    def get_by_short_name(self, short_name: str) -> Optional[Module]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM modules WHERE short_name = %s" if self.manager.db_type != 'sqlite' else "SELECT * FROM modules WHERE short_name = ?"
            cursor.execute(query, (short_name,))
            row = cursor.fetchone()
            return self._to_model(dict(row)) if row else None
        finally:
            conn.close()

class ConfigRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'configs')

    def get_by_module_and_key(self, module_id: int, key: str) -> Optional[Dict[str, Any]]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM configs WHERE module_id = %s AND key = %s" if self.manager.db_type != 'sqlite' else "SELECT * FROM configs WHERE module_id = ? AND key = ?"
            cursor.execute(query, (module_id, key))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

