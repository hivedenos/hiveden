from typing import Generic, TypeVar, Type, List, Optional, Any, Dict

class BaseRepository:
    def __init__(self, manager, table_name: str, model_class: Optional[Type] = None):
        self.manager = manager
        self.table_name = table_name
        self.model_class = model_class

    def _to_model(self, row: Dict[str, Any]) -> Any:
        if self.model_class:
            return self.model_class(**row)
        return row

    def get(self, id: int) -> Optional[Any]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = f"SELECT * FROM {self.table_name} WHERE id = %s" if self.manager.db_type != 'sqlite' else f"SELECT * FROM {self.table_name} WHERE id = ?"
            cursor.execute(query, (id,))
            row = cursor.fetchone()
            return self._to_model(dict(row)) if row else None
        finally:
            conn.close()

    def get_all(self) -> List[Any]:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = f"SELECT * FROM {self.table_name}"
            cursor.execute(query)
            rows = cursor.fetchall()
            return [self._to_model(dict(row)) for row in rows]
        finally:
            conn.close()

    def create(self, model: Optional[Any] = None, **kwargs) -> Any:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            
            data = kwargs
            if model:
                # If model is provided, convert to dict, excluding None values (to let DB defaults work)
                # Assuming pydantic model
                model_data = model.dict(exclude_unset=True) if hasattr(model, 'dict') else model.__dict__
                # Filter out None values for id/created_at if they are None
                model_data = {k: v for k, v in model_data.items() if v is not None}
                data.update(model_data)

            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data)) if self.manager.db_type != 'sqlite' else ', '.join(['?'] * len(data))
            
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            
            if self.manager.db_type == 'sqlite':
                cursor.execute(query, tuple(data.values()))
                last_id = cursor.lastrowid
            else:
                query += " RETURNING id"
                cursor.execute(query, tuple(data.values()))
                last_id = cursor.fetchone()[0]
                
            conn.commit()
            
            # Fetch the created record to return full object/dict
            return self.get(last_id)
        finally:
            conn.close()

    def update(self, id: int, **kwargs) -> Optional[Any]:
        if not kwargs:
            return self.get(id)
            
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            set_clause = ', '.join([f"{k} = %s" for k in kwargs.keys()]) if self.manager.db_type != 'sqlite' else ', '.join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values())
            values.append(id)
            
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s" if self.manager.db_type != 'sqlite' else f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?"
            
            cursor.execute(query, tuple(values))
            conn.commit()
            
            if cursor.rowcount == 0:
                return None
                
            return self.get(id)
        finally:
            conn.close()

    def delete(self, id: int) -> bool:
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = f"DELETE FROM {self.table_name} WHERE id = %s" if self.manager.db_type != 'sqlite' else f"DELETE FROM {self.table_name} WHERE id = ?"
            cursor.execute(query, (id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


