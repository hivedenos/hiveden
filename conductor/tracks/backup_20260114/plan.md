# Implementation Plan - Automated Backups

## Phase 1: Core Backup Logic

- [x] Task: Create backup module structure 4a9a211
  - [ ] Create `src/hiveden/backups/` directory and `__init__.py`.
  - [ ] Define `BackupManager` class interface in `src/hiveden/backups/manager.py`.
- [x] Task: Implement PostgreSQL Backup 1ba5303
  - [ ] Write tests for PostgreSQL backup generation (mocking `pg_dump`).
  - [ ] Implement `pg_dump` wrapper in `BackupManager`.
  - [ ] Implement storage logic for SQL dump files.
- [x] Task: Implement Application Data Backup 4a2ea5e
  - [ ] Write tests for file archiving logic.
  - [ ] Implement file archiving (tar/zip) for specified directories (e.g., `/etc/hiveden`, data dirs).
- [x] Task: Implement Restore Logic 024381f
  - [ ] Write tests for restore process (mocking `pg_restore` and file extraction).
  - [ ] Implement `pg_restore` wrapper.
  - [ ] Implement file extraction logic.
- [x] Task: Conductor - User Manual Verification 'Phase 1: Core Backup Logic' (Protocol in workflow.md) [checkpoint: 7a0313d]

## Phase 2: CLI Integration

- [ ] Task: Create Backup CLI Group
  - [ ] Create `src/hiveden/cli/backup.py`.
  - [ ] Register `backup` command group in `src/hiveden/cli/main.py`.
- [ ] Task: Implement Create Command
  - [ ] Write integration test for `hiveden backup create`.
  - [ ] Implement command to trigger `BackupManager.create_backup()`.
- [ ] Task: Implement List and Restore Commands
  - [ ] Write integration tests for list and restore commands.
  - [ ] Implement `hiveden backup list` and `hiveden backup restore`.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: CLI Integration' (Protocol in workflow.md)

## Phase 3: API & Scheduling

- [ ] Task: Create API Endpoints
  - [ ] Create `src/hiveden/api/routers/backups.py`.
  - [ ] Implement endpoints for create, list, update, delete, and restore.
  - [ ] Register router in `src/hiveden/api/server.py`.
- [ ] Task: Implement Scheduling
  - [ ] Research and select scheduling library (e.g., `APScheduler`) or systemd timer integration.
  - [ ] Implement scheduling logic in `BackupManager`.
  - [ ] Add CLI/API support for configuring schedules.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: API & Scheduling' (Protocol in workflow.md)
