import sqlite3
import psycopg2
from urllib.parse import urlparse

class DatabaseManager:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.parsed_url = urlparse(db_url)
        self.db_type = self.parsed_url.scheme

    def get_connection(self):
        """Get a raw database connection."""
        if self.db_type == 'sqlite':
            # Remove 'sqlite:///' or 'sqlite://' prefix
            path = self.db_url.replace('sqlite:///', '').replace('sqlite://', '')
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            return conn
        elif self.db_type == 'postgresql' or self.db_type == 'postgres':
            return psycopg2.connect(self.db_url)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def execute_script(self, script: str):
        """Execute a raw SQL script."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.executescript(script) if self.db_type == 'sqlite' else cursor.execute(script)
            conn.commit()
        finally:
            conn.close()

    def reset_db(self):
        """Reset the database by dropping and recreating all tables."""
        # Define schema
        # Note: SQLite and Postgres have slightly different syntax for some things (e.g. AUTOINCREMENT vs SERIAL)
        # We'll try to use compatible SQL or branch based on type.
        
        drop_script = """
        DROP TABLE IF EXISTS logs;
        DROP TABLE IF EXISTS container_attributes;
        DROP TABLE IF EXISTS containers;
        DROP TABLE IF EXISTS configs;
        DROP TABLE IF EXISTS modules;
        """
        
        create_script_sqlite = """
        CREATE TABLE modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            short_name TEXT UNIQUE NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
        );

        CREATE TABLE containers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('docker', 'lxc')),
            is_container BOOLEAN DEFAULT 0,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP
        );

        CREATE TABLE container_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            container_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP,
            FOREIGN KEY(container_id) REFERENCES containers(id) ON DELETE CASCADE
        );

        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            log TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
        );
        """
        
        create_script_postgres = """
        CREATE TABLE modules (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            short_name TEXT UNIQUE NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE configs (
            id SERIAL PRIMARY KEY,
            module_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
        );

        CREATE TABLE containers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('docker', 'lxc')),
            is_container BOOLEAN DEFAULT FALSE,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP
        );

        CREATE TABLE container_attributes (
            id SERIAL PRIMARY KEY,
            container_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP,
            FOREIGN KEY(container_id) REFERENCES containers(id) ON DELETE CASCADE
        );

        CREATE TABLE logs (
            id SERIAL PRIMARY KEY,
            module_id INTEGER NOT NULL,
            log TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(module_id) REFERENCES modules(id) ON DELETE CASCADE
        );
        """
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Drop tables
            if self.db_type == 'sqlite':
                cursor.executescript(drop_script)
                cursor.executescript(create_script_sqlite)
            else:
                cursor.execute(drop_script)
                cursor.execute(create_script_postgres)
                
            conn.commit()
        finally:
            conn.close()

