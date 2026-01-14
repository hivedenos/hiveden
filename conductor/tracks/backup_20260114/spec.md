# Specification: Automated Backups

## Context
Data integrity and recovery are critical for any server management system. This track aims to implement a robust backup solution for both the PostgreSQL database used by Hiveden and the application's critical data.

## Goals
1.  **PostgreSQL Backup:**
    -   Automate the backup process for PostgreSQL databases.
    -   Ensure backups are stored securely with timestamped filenames.
    -   Provide a mechanism to restore from these backups.

2.  **Application Data Backup:**
    -   Identify and backup critical Hiveden application data (configuration files, etc.).
    -   **Lifecycle Management:** Ensure data consistency by stopping the relevant container before backup and starting it immediately after.
    -   Ensure data can be restored in case of corruption or loss.

3.  **Automation & Scheduling:**
    -   Allow users to schedule backups (e.g., daily, weekly).
    -   Integrate with the existing job scheduling system if available, or implement a new one.

4.  **Configuration & Management:**
    -   Centralized configuration for backup locations, retention policies, and targets.
    -   Prevent backups if configuration is invalid or missing.

## Requirements

### Storage & Configuration
-   **Backup Directory:** Must be configurable via the standard Hiveden configuration system.
-   **Filenames:** Must contain the date and time of the backup (e.g., `db_name_YYYYMMDD_HHMMSS.sql`).
-   **Retention Policy:**
    -   Configurable number of backups to keep.
    -   Automated cleanup of old backups based on count.

### API Endpoints
-   **Configuration Management:**
    -   `GET/PUT /api/config/backups`: Manage backup directory and retention settings.
-   **Backup Operations:**
    -   `GET /api/backups`: Retrieve all backups.
        -   **Query Params:** `type` (database/app), `target` (db_name/app_name).
    -   `POST /api/backups`: Trigger a new backup.
    -   `POST /api/backups/restore`: Restore a backup.

### CLI Commands
-   `hiveden backup create`: Trigger an immediate backup.
-   `hiveden backup list`: List available backups with filtering options.
-   `hiveden backup restore <backup_id>`: Restore from a specific backup.
-   `hiveden backup schedule`: Configure backup schedules.

## Technical Considerations
-   **Container Integration:** Use Hiveden's Docker/LXC modules to control container state during application backups.
-   **Validation:** All backup operations must validate configuration existence before proceeding.
-   **Tools:**
    -   `pg_dump`/`pg_restore` for PostgreSQL.
    -   `tar` for application files.