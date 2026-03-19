import logging
import os
import re
import shutil
import traceback
from datetime import datetime
from typing import List

from hiveden.explorer.manager import ExplorerManager
from hiveden.explorer.models import ExplorerOperation, OperationStatus
from hiveden.explorer.operations import ExplorerService

logger = logging.getLogger(__name__)


def _is_cancelled(manager: ExplorerManager, op_id: str) -> bool:
    current = manager.get_operation(op_id)
    return bool(current and current.status == OperationStatus.CANCELLED)


def _mark_cancelled(
    op: ExplorerOperation,
    manager: ExplorerManager,
    result=None,
):
    op.status = OperationStatus.CANCELLED
    op.error_message = op.error_message or "Operation cancelled"
    op.completed_at = datetime.utcnow()
    if result is not None:
        op.result = result
    manager.update_operation(op)


def perform_search(
    op_id: str,
    path: str,
    pattern: str,
    use_regex: bool,
    case_sensitive: bool,
    type_filter: str,
    show_hidden: bool,
):
    manager = ExplorerManager()
    service = ExplorerService()

    logger.info(
        "Starting search operation %s in %s with pattern %s", op_id, path, pattern
    )

    op = manager.get_operation(op_id)
    if not op:
        logger.error("Operation %s not found", op_id)
        return

    op.status = OperationStatus.IN_PROGRESS
    manager.update_operation(op)

    matches = []
    total_scanned = 0
    start_time = datetime.now()

    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        if not use_regex:
            pattern = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")

        regex = re.compile(pattern, flags)

        for root, dirs, files in os.walk(path):
            if _is_cancelled(manager, op_id):
                _mark_cancelled(
                    op,
                    manager,
                    {
                        "matches": matches,
                        "total_matches": len(matches),
                        "search_time_seconds": (
                            datetime.now() - start_time
                        ).total_seconds(),
                    },
                )
                return

            if not show_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                files = [f for f in files if not f.startswith(".")]

            if type_filter in ["all", "directory"]:
                for directory in dirs:
                    if _is_cancelled(manager, op_id):
                        _mark_cancelled(
                            op,
                            manager,
                            {
                                "matches": matches,
                                "total_matches": len(matches),
                                "search_time_seconds": (
                                    datetime.now() - start_time
                                ).total_seconds(),
                            },
                        )
                        return
                    total_scanned += 1
                    if regex.search(directory):
                        try:
                            full_path = os.path.join(root, directory)
                            matches.append(service.get_file_entry(full_path).dict())
                        except Exception as exc:
                            logger.warning(
                                "Error getting file entry for %s: %s", directory, exc
                            )

            if type_filter in ["all", "file"]:
                for filename in files:
                    if _is_cancelled(manager, op_id):
                        _mark_cancelled(
                            op,
                            manager,
                            {
                                "matches": matches,
                                "total_matches": len(matches),
                                "search_time_seconds": (
                                    datetime.now() - start_time
                                ).total_seconds(),
                            },
                        )
                        return
                    total_scanned += 1
                    if regex.search(filename):
                        try:
                            full_path = os.path.join(root, filename)
                            matches.append(service.get_file_entry(full_path).dict())
                        except Exception as exc:
                            logger.warning(
                                "Error getting file entry for %s: %s", filename, exc
                            )

            if total_scanned % 100 == 0:
                op.processed_items = total_scanned
                manager.update_operation(op)

        search_time = (datetime.now() - start_time).total_seconds()
        op.result = {
            "matches": matches,
            "total_matches": len(matches),
            "search_time_seconds": search_time,
        }
        op.status = OperationStatus.COMPLETED
        op.processed_items = total_scanned
        op.completed_at = datetime.utcnow()
        manager.update_operation(op)
    except Exception as exc:
        logger.error("Search operation %s failed: %s", op_id, exc, exc_info=True)
        op.status = OperationStatus.FAILED
        op.error_message = str(exc)
        op.completed_at = datetime.utcnow()
        manager.update_operation(op)


def perform_paste(
    op_id: str,
    source_paths: List[str],
    dest_path: str,
    conflict_resolution: str,
    rename_pattern: str,
):
    manager = ExplorerManager()
    op = manager.get_operation(op_id)
    if not op:
        return

    op.status = OperationStatus.IN_PROGRESS
    op.total_items = len(source_paths)
    manager.update_operation(op)

    processed = 0
    errors = []

    try:
        is_move = op.operation_type == "move"

        for src in source_paths:
            if _is_cancelled(manager, op_id):
                _mark_cancelled(
                    op,
                    manager,
                    {"processed_items": processed, "total_items": len(source_paths)},
                )
                return

            if not os.path.exists(src):
                errors.append(f"Source not found: {src}")
                continue

            src_name = os.path.basename(src)
            final_dest = os.path.join(dest_path, src_name)

            if os.path.exists(final_dest):
                if conflict_resolution == "skip":
                    continue
                if conflict_resolution == "overwrite":
                    if os.path.isdir(final_dest):
                        shutil.rmtree(final_dest)
                    else:
                        os.remove(final_dest)
                elif conflict_resolution == "rename":
                    base, ext = os.path.splitext(src_name)
                    counter = 1
                    while os.path.exists(final_dest):
                        new_name = rename_pattern.format(name=base, n=counter) + ext
                        final_dest = os.path.join(dest_path, new_name)
                        counter += 1
                        if counter > 1000:
                            raise Exception("Too many name conflicts")

            if is_move:
                shutil.move(src, final_dest)
            else:
                if os.path.isdir(src):
                    shutil.copytree(src, final_dest)
                else:
                    shutil.copy2(src, final_dest)

            if _is_cancelled(manager, op_id):
                if os.path.exists(final_dest):
                    if os.path.isdir(final_dest):
                        shutil.rmtree(final_dest)
                    else:
                        os.remove(final_dest)
                _mark_cancelled(
                    op,
                    manager,
                    {"processed_items": processed, "total_items": len(source_paths)},
                )
                return

            processed += 1
            op.processed_items = processed
            op.progress = int((processed / len(source_paths)) * 100)
            manager.update_operation(op)

        if errors:
            op.error_message = "; ".join(errors)
            op.status = (
                OperationStatus.COMPLETED if processed > 0 else OperationStatus.FAILED
            )
        else:
            op.status = OperationStatus.COMPLETED

        op.completed_at = datetime.utcnow()
        manager.update_operation(op)
    except Exception as exc:
        op.status = OperationStatus.FAILED
        op.error_message = str(exc) + "\n" + traceback.format_exc()
        op.completed_at = datetime.utcnow()
        manager.update_operation(op)
