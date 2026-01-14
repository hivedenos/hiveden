# Implementation Plan - Automated Backups

## Phase 1: Core Backup Logic
- [x] Task: Create backup module structure [4a9a211]
    - [x] Create `src/hiveden/backups/` directory and `__init__.py`.
    - [x] Define `BackupManager` class interface in `src/hiveden/backups/manager.py`.
- [x] Task: Implement PostgreSQL Backup [1ba5303]
    - [x] Write tests for PostgreSQL backup generation (mocking `pg_dump`).
    - [x] Implement `pg_dump` wrapper in `BackupManager`.
    - [x] Implement storage logic for SQL dump files.
- [x] Task: Implement Application Data Backup [4a2ea5e]
    - [x] Write tests for file archiving logic.
    - [x] Implement file archiving (tar/zip) for specified directories (e.g., `/etc/hiveden`, data dirs).
- [x] Task: Implement Restore Logic [024381f]
    - [x] Write tests for restore process (mocking `pg_restore` and file extraction).
    - [x] Implement `pg_restore` wrapper.
    - [x] Implement file extraction logic.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Core Backup Logic' (Protocol in workflow.md) [checkpoint: 7a0313d]

## Phase 1.5: Advanced Logic & Configuration
- [x] Task: Implement Configuration Validation 61ed3c2
    - [ ] Add config dependency to `BackupManager`.
    - [ ] Implement validation logic: ensure backup directory is set and exists.
    - [ ] Prevent backup creation if validation fails.
- [x] Task: Implement Container Lifecycle Management ab99d67
    - [ ] Import `DockerManager` or equivalent service.
    - [ ] Update `create_app_data_backup` to accept a `container_name`.
    - [ ] Implement logic: Stop container -> Backup -> Start container.
    - [ ] Ensure container is restarted even if backup fails (try/finally).
- [x] Task: Implement Retention Policy - [~] Task: Implement Retention Policy & Listing Listing 115ab39
    - [ ] Implement `list_backups` method with filtering (type, target).
    - [ ] Implement `enforce_retention_policy` method to delete old backups.
    - [ ] Integrate retention check into backup creation flow.
- [x] Task: Conductor - User Manual Verification 'Phase 1.5: Advanced Logic - [ ] Task: Conductor - User Manual Verification 'Phase 1.5: Advanced Logic & Configuration' (Protocol in workflow.md) Configuration' (Protocol in workflow.md) [checkpoint: ec32502]

## Phase 2: CLI Integration
- [ ] Task: Create Backup CLI Group
    - [ ] Create `src/hiveden/cli/backup.py`.
    - [ ] Register `backup` command group in `src/hiveden/cli/main.py`.
- [ ] Task: Implement Create Command with Validation
    - [ ] Wire up CLI to `BackupManager`.
    - [ ] Handle validation errors gracefully.
- [ ] Task: Implement List and Restore Commands
    - [ ] Implement `hiveden backup list` using new filtering logic.
    - [ ] Implement `hiveden backup restore`.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI Integration' (Protocol in workflow.md)

## Phase 3: API & Scheduling
- [x] Task: Create API Endpoints d38404a
    - [ ] Create `src/hiveden/api/routers/backups.py`.
    - [ ] Implement `GET /api/backups` with query params.
    - [ ] Implement `POST /api/backups` and `POST /api/backups/restore`.
    - [ ] Implement `GET/PUT /api/config/backups` for directory and retention settings.
- [x] Task: Implement Scheduling 4bef2b7
    - [ ] Implement scheduling logic in `BackupManager`.
    - [ ] Add CLI/API support for configuring schedules.
- [x] Task: Conductor - User Manual Verification 'Phase 3: API - [ ] Task: Conductor - User Manual Verification 'Phase 3: API & Scheduling' (Protocol in workflow.md) Scheduling' (Protocol in workflow.md) [checkpoint: 4bef2b7]