from typing import Optional, Dict, Any, List
from hiveden.db.repositories.base import BaseRepository
from hiveden.db.models.template import ContainerTemplate, ContainerTemplateAttribute

class ContainerTemplateRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'container_templates', model_class=ContainerTemplate)

    def get_by_type(self, type: str) -> List[ContainerTemplate]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM container_templates WHERE type = %s AND deleted_at IS NULL" if self.manager.db_type != 'sqlite' else "SELECT * FROM container_templates WHERE type = ? AND deleted_at IS NULL"
            cursor.execute(query, (type,))
            rows = cursor.fetchall()
            return [self._to_model(dict(row)) for row in rows]
        finally:
            conn.close()

    def soft_delete(self, id: int) -> bool:
        """Soft delete a template by setting deleted_at."""
        import datetime
        now = datetime.datetime.utcnow()
        return self.update(id, deleted_at=now) is not None

class ContainerTemplateAttributeRepository(BaseRepository):
    def __init__(self, manager):
        super().__init__(manager, 'container_templates_attributes', model_class=ContainerTemplateAttribute)

    def get_by_template_id(self, template_id: int) -> List[ContainerTemplateAttribute]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM container_templates_attributes WHERE container_template_id = %s AND deleted_at IS NULL" if self.manager.db_type != 'sqlite' else "SELECT * FROM container_templates_attributes WHERE container_template_id = ? AND deleted_at IS NULL"
            cursor.execute(query, (template_id,))
            rows = cursor.fetchall()
            return [self._to_model(dict(row)) for row in rows]
        finally:
            conn.close()
