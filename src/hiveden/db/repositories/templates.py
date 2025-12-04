from typing import Optional, Dict, Any, List
from hiveden.db.repositories.base import BaseRepository
from hiveden.db.models.template import Container, ContainerAttribute

class ContainerRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'containers', model_class=Container)

    def get_by_type(self, type: str) -> List[Container]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM containers WHERE type = %s AND deleted_at IS NULL" if self.manager.db_type != 'sqlite' else "SELECT * FROM containers WHERE type = ? AND deleted_at IS NULL"
            cursor.execute(query, (type,))
            rows = cursor.fetchall()
            return [self._to_model(dict(row)) for row in rows]
        finally:
            conn.close()

    def create(self, data: Dict[str, Any]) -> Optional[Container]:
        """Create a new container record."""
        return super().create(data)

    def soft_delete(self, id: int) -> bool:
        """Soft delete a container by setting deleted_at."""
        import datetime
        now = datetime.datetime.utcnow()
        return self.update(id, deleted_at=now) is not None

class ContainerAttributeRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'container_attributes', model_class=ContainerAttribute)

    def get_by_container_id(self, container_id: int) -> List[ContainerAttribute]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM container_attributes WHERE container_id = %s AND deleted_at IS NULL" if self.manager.db_type != 'sqlite' else "SELECT * FROM container_attributes WHERE container_id = ? AND deleted_at IS NULL"
            cursor.execute(query, (container_id,))
            rows = cursor.fetchall()
            return [self._to_model(dict(row)) for row in rows]
        finally:
            conn.close()

    def create(self, data: Dict[str, Any]) -> Optional[ContainerAttribute]:
        """Create a new container attribute."""
        return super().create(data)
