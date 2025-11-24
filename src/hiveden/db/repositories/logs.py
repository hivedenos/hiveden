from typing import List, Dict, Any
from hiveden.db.repositories.base import BaseRepository

class LogRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'logs')

    def get_by_module_id(self, module_id: int) -> List[Dict[str, Any]]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM logs WHERE module_id = %s ORDER BY created_at DESC, id DESC" if self.manager.db_type != 'sqlite' else "SELECT * FROM logs WHERE module_id = ? ORDER BY created_at DESC, id DESC"
            cursor.execute(query, (module_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
