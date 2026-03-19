from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, FileResponse
from typing import Any, Dict, List, Optional, cast
import os
from datetime import datetime
import logging

from hiveden.explorer.models import (
    DirectoryListingResponse,
    FileEntry,
    FilePropertyResponse,
    CreateDirectoryRequest,
    DeleteRequest,
    DeleteResponse,
    RenameRequest,
    GenericResponse,
    UploadPrepareRequest,
    UploadPrepareResponse,
    UploadResponse,
    ClipboardCopyRequest,
    ClipboardPasteRequest,
    ClipboardStatusResponse,
    LocationCreateRequest,
    LocationUpdateRequest,
    FilesystemLocation,
    SearchRequest,
    OperationResponse,
    ExplorerOperation,
    ConfigUpdateRequest,
    ExplorerConfig,
    SortBy,
    SortOrder,
    OperationStatus,
    OperationType,
)
from hiveden.explorer.manager import ExplorerManager
from hiveden.explorer.operations import ExplorerService, UploadCancelledError
from hiveden.explorer.tasks import perform_search, perform_paste

router = APIRouter(prefix="/explorer", tags=["Explorer"])

logger = logging.getLogger(__name__)

# In-memory clipboard store
# { session_id: { operation: "copy"|"cut", paths: [], timestamp: datetime } }
clipboard_store = {}


def get_manager():
    return ExplorerManager()


def get_service():
    config = get_manager().get_config()
    root = config.get("root_directory", "/")
    return ExplorerService(root_directory=root)


def _get_upload_size(upload: UploadFile) -> int:
    upload.file.seek(0, os.SEEK_END)
    size = upload.file.tell()
    upload.file.seek(0)
    return size


def _build_upload_operation_result(
    op_id: str,
    status: str,
    files_progress: List[Dict[str, Any]],
) -> Dict[str, Any]:
    processed_items = sum(
        1
        for item in files_progress
        if item["status"] in {"completed", "failed", "skipped", "cancelled"}
    )
    total_items = len(files_progress)
    total_bytes = sum(item["size"] for item in files_progress)
    uploaded_bytes = sum(item["uploaded_bytes"] for item in files_progress)
    progress = 100 if total_bytes == 0 and total_items else 0
    if total_bytes > 0:
        progress = int((uploaded_bytes / total_bytes) * 100)

    summary = {
        "created": sum(
            1
            for item in files_progress
            if item.get("result", {}).get("outcome") == "created"
        ),
        "overwritten": sum(
            1
            for item in files_progress
            if item.get("result", {}).get("outcome") == "overwritten"
        ),
        "skipped": sum(1 for item in files_progress if item["status"] == "skipped"),
        "failed": sum(1 for item in files_progress if item["status"] == "failed"),
        "cancelled": sum(
            1 for item in files_progress if item["status"] == OperationStatus.CANCELLED
        ),
        "completed": sum(
            1 for item in files_progress if item["status"] == OperationStatus.COMPLETED
        ),
        "in_progress": sum(
            1
            for item in files_progress
            if item["status"] == OperationStatus.IN_PROGRESS
        ),
        "pending": sum(
            1 for item in files_progress if item["status"] == OperationStatus.PENDING
        ),
    }

    return {
        "operation_id": op_id,
        "status": status,
        "progress": progress,
        "total_items": total_items,
        "processed_items": processed_items,
        "uploaded_bytes": uploaded_bytes,
        "total_bytes": total_bytes,
        "summary": summary,
        "files": files_progress,
    }


def _sync_upload_operation(
    manager: ExplorerManager,
    op: ExplorerOperation,
    files_progress: List[Dict[str, Any]],
    status: str,
    error_message: Optional[str] = None,
):
    payload = _build_upload_operation_result(op.id, status, files_progress)
    op.status = status
    op.progress = payload["progress"]
    op.total_items = payload["total_items"]
    op.processed_items = payload["processed_items"]
    op.result = payload
    op.error_message = error_message
    if status in {
        OperationStatus.COMPLETED,
        OperationStatus.FAILED,
        OperationStatus.CANCELLED,
    }:
        op.completed_at = datetime.utcnow()
    manager.update_operation(op)


def _build_upload_file_progress(
    destination: str,
    filename: str,
    size: int,
    overwrite: bool,
) -> Dict[str, Any]:
    target_path = os.path.join(destination, os.path.basename(filename))
    conflict = os.path.exists(target_path)
    return {
        "name": filename,
        "size": size,
        "uploaded_bytes": 0,
        "progress": 0 if size else 100,
        "status": OperationStatus.PENDING,
        "error_message": None,
        "result": {
            "path": target_path,
            "conflict": conflict,
            "outcome": "overwrite"
            if conflict and overwrite
            else "conflict"
            if conflict
            else "create",
        },
    }


def _create_upload_operation(
    manager: ExplorerManager,
    destination: str,
    files_progress: List[Dict[str, Any]],
) -> ExplorerOperation:
    op = manager.create_operation(OperationType.UPLOAD, OperationStatus.PENDING)
    op.destination_path = destination
    op.source_paths = [item["name"] for item in files_progress]
    _sync_upload_operation(manager, op, files_progress, OperationStatus.PENDING)
    return op


def _get_or_create_upload_operation(
    manager: ExplorerManager,
    destination: str,
    files_progress: List[Dict[str, Any]],
    operation_id: Optional[str],
) -> ExplorerOperation:
    if not operation_id:
        return _create_upload_operation(manager, destination, files_progress)

    op = manager.get_operation(operation_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    if op.operation_type != OperationType.UPLOAD:
        raise HTTPException(status_code=400, detail="Operation is not an upload")
    if op.status == OperationStatus.CANCELLED:
        raise HTTPException(
            status_code=409, detail="Upload operation has been cancelled"
        )
    op.destination_path = destination
    op.source_paths = [item["name"] for item in files_progress]
    _sync_upload_operation(manager, op, files_progress, OperationStatus.PENDING)
    return op


def _upload_error_summary(items: List[Dict[str, Any]]) -> Optional[str]:
    message = "; ".join(
        f"{item['name']}: {item['error_message']}"
        for item in items
        if item.get("error_message")
    )
    return message or None


def _get_operation_files_progress(op: ExplorerOperation) -> List[Dict[str, Any]]:
    if isinstance(op.result, dict) and isinstance(op.result.get("files"), list):
        return [dict(item) for item in op.result["files"]]
    return []


def _find_or_create_upload_file_progress(
    files_progress: List[Dict[str, Any]],
    destination: str,
    filename: str,
    size: int,
    overwrite: bool,
) -> Dict[str, Any]:
    for item in files_progress:
        if item.get("name") == filename:
            item["size"] = size or item.get("size", 0)
            if item.get("result") is None:
                item["result"] = _build_upload_file_progress(
                    destination,
                    filename,
                    item["size"],
                    overwrite,
                )["result"]
            return item

    item = _build_upload_file_progress(destination, filename, size, overwrite)
    files_progress.append(item)
    return item


def _derive_upload_status(files_progress: List[Dict[str, Any]]) -> str:
    statuses = [item["status"] for item in files_progress]
    if not statuses:
        return OperationStatus.PENDING
    if any(status == OperationStatus.IN_PROGRESS for status in statuses):
        return OperationStatus.IN_PROGRESS
    if all(status == OperationStatus.PENDING for status in statuses):
        return OperationStatus.PENDING
    if any(status == OperationStatus.PENDING for status in statuses):
        return OperationStatus.IN_PROGRESS
    if any(status == OperationStatus.CANCELLED for status in statuses):
        return OperationStatus.CANCELLED
    if all(status == "failed" for status in statuses):
        return OperationStatus.FAILED
    return OperationStatus.COMPLETED


# --- Navigation ---


@router.get("/list", response_model=DirectoryListingResponse)
def list_directory(
    path: str,
    show_hidden: bool = False,
    sort_by: SortBy = SortBy.NAME,
    sort_order: SortOrder = SortOrder.ASC,
):
    service = get_service()
    try:
        entries, count, total_size = service.list_directory(
            path, show_hidden, sort_by, sort_order
        )
        return DirectoryListingResponse(
            current_path=path,
            parent_path=os.path.dirname(path),
            entries=entries,
            total_entries=count,
            total_size=total_size,
            total_size_human=service._human_readable_size(total_size),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/navigate", response_model=DirectoryListingResponse)
def navigate(
    body: dict,  # Hack to allow flexible body or define model.
    # Req doc says {path, show_hidden}. Let's make a model or use param.
):
    path = body.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Path required")
    show_hidden = body.get("show_hidden", False)

    return list_directory(path, show_hidden=show_hidden)


@router.get("/properties", response_model=FilePropertyResponse)
def get_properties(path: str):
    service = get_service()
    try:
        entry = service.get_file_entry(path)
        return FilePropertyResponse(entry=entry)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Path not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cwd")
def get_cwd():
    # Stateless, returns root as per reqs
    service = get_service()
    return {"success": True, "current_path": service.root_directory, "is_root": True}


# --- File Operations ---


@router.post("/create-directory", status_code=201)
def create_directory(req: CreateDirectoryRequest):
    service = get_service()
    try:
        new_path = service.create_directory(req.path, req.parents)
        return {
            "success": True,
            "message": "Directory created successfully",
            "path": new_path,
        }
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Path already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/prepare", response_model=UploadPrepareResponse, status_code=201)
def prepare_upload(req: UploadPrepareRequest):
    service = get_service()
    manager = get_manager()
    destination_dir = service._resolve_path(req.destination)
    if not os.path.exists(destination_dir):
        raise HTTPException(
            status_code=404, detail=f"Path not found: {req.destination}"
        )
    if not os.path.isdir(destination_dir):
        raise HTTPException(
            status_code=400, detail=f"Path is not a directory: {req.destination}"
        )

    files_progress = [
        _build_upload_file_progress(
            destination_dir, file.name, file.size, req.overwrite
        )
        for file in req.files
    ]
    op = _create_upload_operation(manager, destination_dir, files_progress)
    op = manager.get_operation(op.id) or op
    return UploadPrepareResponse(
        success=True,
        message="Upload prepared",
        operation_id=op.id,
        operation=op,
        destination=destination_dir,
        files=files_progress,
    )


@router.post("/upload/conflicts")
def check_upload_conflicts(req: UploadPrepareRequest):
    service = get_service()
    destination_dir = service._resolve_path(req.destination)
    if not os.path.exists(destination_dir):
        raise HTTPException(
            status_code=404, detail=f"Path not found: {req.destination}"
        )
    if not os.path.isdir(destination_dir):
        raise HTTPException(
            status_code=400, detail=f"Path is not a directory: {req.destination}"
        )
    files_progress = [
        _build_upload_file_progress(
            destination_dir, file.name, file.size, req.overwrite
        )
        for file in req.files
    ]
    return {
        "success": True,
        "message": "Upload conflicts checked",
        "destination": destination_dir,
        "files": files_progress,
    }


@router.put("/upload/stream/{operation_id}", response_model=UploadResponse)
async def stream_upload_file(
    operation_id: str,
    request: Request,
    filename: str = Query(...),
    size: int = Query(0, ge=0),
    overwrite: bool = Query(False),
):
    manager = get_manager()
    service = get_service()
    op = manager.get_operation(operation_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    if op.operation_type != OperationType.UPLOAD:
        raise HTTPException(status_code=400, detail="Operation is not an upload")
    if op.status == OperationStatus.CANCELLED:
        raise HTTPException(
            status_code=409, detail="Upload operation has been cancelled"
        )
    if not op.destination_path:
        raise HTTPException(
            status_code=400, detail="Upload operation has no destination"
        )

    destination_dir = service._resolve_path(op.destination_path)
    if not os.path.exists(destination_dir):
        raise HTTPException(
            status_code=404, detail=f"Path not found: {op.destination_path}"
        )
    if not os.path.isdir(destination_dir):
        raise HTTPException(
            status_code=400, detail=f"Path is not a directory: {op.destination_path}"
        )

    expected_size = size or int(request.headers.get("content-length", "0") or 0)
    files_progress = _get_operation_files_progress(op)
    item = _find_or_create_upload_file_progress(
        files_progress,
        destination_dir,
        filename,
        expected_size,
        overwrite,
    )

    if item["status"] == OperationStatus.COMPLETED and not overwrite:
        completed_op = manager.get_operation(op.id) or op
        raise HTTPException(
            status_code=409, detail=f"File already uploaded: {filename}"
        )

    target_path = os.path.join(destination_dir, os.path.basename(filename))
    conflict = os.path.exists(target_path)
    if conflict and not overwrite:
        item["status"] = "skipped"
        item["error_message"] = f"Destination exists: {target_path}"
        item["result"] = {
            "path": target_path,
            "conflict": True,
            "outcome": "skipped",
        }
        overall_status = _derive_upload_status(files_progress)
        _sync_upload_operation(
            manager,
            op,
            files_progress,
            overall_status,
            error_message=_upload_error_summary([item]),
        )
        raise HTTPException(status_code=409, detail=item["error_message"])

    item["size"] = expected_size
    item["uploaded_bytes"] = 0
    item["progress"] = 0 if expected_size else 100
    item["status"] = OperationStatus.IN_PROGRESS
    item["error_message"] = None
    item["result"] = {
        "path": target_path,
        "conflict": conflict,
        "outcome": "overwrite" if conflict and overwrite else "create",
    }
    _sync_upload_operation(manager, op, files_progress, OperationStatus.IN_PROGRESS)

    def is_cancelled() -> bool:
        current = manager.get_operation(op.id)
        return bool(current and current.status == OperationStatus.CANCELLED)

    try:
        uploaded_bytes = 0
        with open(target_path, "wb") as output:
            async for chunk in request.stream():
                if is_cancelled():
                    raise UploadCancelledError(f"Upload cancelled: {filename}")
                if not chunk:
                    continue
                output.write(chunk)
                uploaded_bytes += len(chunk)
                item["uploaded_bytes"] = uploaded_bytes
                if expected_size > 0:
                    item["progress"] = int((uploaded_bytes / expected_size) * 100)
                _sync_upload_operation(
                    manager, op, files_progress, OperationStatus.IN_PROGRESS
                )

        if expected_size == 0:
            item["size"] = uploaded_bytes
            item["progress"] = 100
        else:
            item["uploaded_bytes"] = uploaded_bytes
            item["progress"] = min(100, int((uploaded_bytes / expected_size) * 100))
        entry = service.get_file_entry(target_path)
        item["status"] = OperationStatus.COMPLETED
        item["result"] = {
            "path": entry.path,
            "conflict": conflict,
            "outcome": "overwritten" if conflict and overwrite else "created",
        }
    except UploadCancelledError as exc:
        if os.path.exists(target_path):
            os.remove(target_path)
        item["status"] = OperationStatus.CANCELLED
        item["error_message"] = str(exc)
    except Exception as exc:
        if os.path.exists(target_path):
            os.remove(target_path)
        item["status"] = "failed"
        item["error_message"] = str(exc)
        overall_status = _derive_upload_status(files_progress)
        _sync_upload_operation(
            manager,
            op,
            files_progress,
            overall_status,
            error_message=_upload_error_summary([item]),
        )
        raise HTTPException(status_code=500, detail=str(exc))

    overall_status = _derive_upload_status(files_progress)
    _sync_upload_operation(
        manager,
        op,
        files_progress,
        overall_status,
        error_message=_upload_error_summary(files_progress),
    )
    completed_op = manager.get_operation(op.id) or op
    uploaded = []
    if item["status"] == OperationStatus.COMPLETED:
        uploaded.append(service.get_file_entry(target_path))

    response = UploadResponse(
        success=item["status"] == OperationStatus.COMPLETED,
        message="File uploaded"
        if uploaded
        else item.get("error_message") or "Upload incomplete",
        operation_id=op.id,
        operation=completed_op,
        destination=destination_dir,
        uploaded=uploaded,
    )
    if item["status"] != OperationStatus.COMPLETED:
        return JSONResponse(status_code=207, content=response.model_dump(mode="json"))
    return response


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_files(
    destination: str = Form(...),
    overwrite: bool = Form(False),
    operation_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
):
    manager = get_manager()
    service = get_service()
    destination_dir = service._resolve_path(destination)
    uploaded = []
    failed = []

    files_progress = [
        _build_upload_file_progress(
            destination_dir,
            upload.filename or "",
            _get_upload_size(upload),
            overwrite,
        )
        for upload in files
    ]
    op = _get_or_create_upload_operation(
        manager,
        destination_dir,
        files_progress,
        operation_id,
    )

    try:
        op.completed_at = None
        _sync_upload_operation(manager, op, files_progress, OperationStatus.IN_PROGRESS)

        for index, upload in enumerate(files):
            item = files_progress[index]
            if not upload.filename:
                item["status"] = "failed"
                item["error_message"] = "Uploaded file is missing a filename"
                failed.append(item)
                _sync_upload_operation(
                    manager, op, files_progress, OperationStatus.IN_PROGRESS
                )
                continue

            upload.file.seek(0)
            item["status"] = OperationStatus.IN_PROGRESS
            _sync_upload_operation(
                manager, op, files_progress, OperationStatus.IN_PROGRESS
            )

            def is_cancelled() -> bool:
                current = manager.get_operation(op.id)
                return bool(current and current.status == OperationStatus.CANCELLED)

            def on_progress(uploaded_bytes: int, current: Dict[str, Any] = item):
                current["uploaded_bytes"] = uploaded_bytes
                current["progress"] = (
                    100
                    if current["size"] == 0
                    else int((uploaded_bytes / current["size"]) * 100)
                )
                _sync_upload_operation(
                    manager, op, files_progress, OperationStatus.IN_PROGRESS
                )

            try:
                entry = cast(Any, service).save_uploaded_file(
                    destination=destination_dir,
                    filename=upload.filename,
                    file_obj=upload.file,
                    size=item["size"],
                    overwrite=overwrite,
                    progress_callback=on_progress,
                    cancel_callback=is_cancelled,
                )
                item["uploaded_bytes"] = item["size"]
                item["progress"] = 100
                item["status"] = OperationStatus.COMPLETED
                item["result"] = {
                    "path": entry.path,
                    "conflict": item["result"]["conflict"],
                    "outcome": "overwritten"
                    if overwrite and item["result"]["conflict"]
                    else "created",
                }
                uploaded.append(entry)
            except FileExistsError as exc:
                item["status"] = "skipped"
                item["error_message"] = str(exc)
                item["result"] = {
                    "path": item["result"]["path"],
                    "conflict": True,
                    "outcome": "skipped",
                }
                failed.append(item)
            except UploadCancelledError as exc:
                item["status"] = OperationStatus.CANCELLED
                item["error_message"] = str(exc)
                failed.append(item)
                _sync_upload_operation(
                    manager,
                    op,
                    files_progress,
                    OperationStatus.CANCELLED,
                    error_message=_upload_error_summary(failed),
                )
                break
            except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
                item["status"] = "failed"
                item["error_message"] = str(exc)
                failed.append(item)

            _sync_upload_operation(
                manager, op, files_progress, OperationStatus.IN_PROGRESS
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error uploading files to %s: %s", destination_dir, exc)
        _sync_upload_operation(
            manager, op, files_progress, OperationStatus.FAILED, error_message=str(exc)
        )
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for upload in files:
            await upload.close()

    final_status = OperationStatus.COMPLETED
    final_message = f"Uploaded {len(uploaded)} file(s)"
    if any(item["status"] == OperationStatus.CANCELLED for item in files_progress):
        final_status = OperationStatus.CANCELLED
        final_message = "Upload cancelled"
    elif failed and uploaded:
        final_message = f"Uploaded {len(uploaded)} of {len(files)} file(s)"
    elif failed and not uploaded:
        final_status = OperationStatus.FAILED
        final_message = "Upload failed"

    _sync_upload_operation(
        manager,
        op,
        files_progress,
        final_status,
        error_message=_upload_error_summary(failed),
    )
    completed_op = manager.get_operation(op.id) or op
    response = UploadResponse(
        success=not failed and final_status != OperationStatus.CANCELLED,
        message=final_message,
        operation_id=op.id,
        operation=completed_op,
        destination=destination_dir,
        uploaded=uploaded,
    )
    if failed or final_status == OperationStatus.CANCELLED:
        return JSONResponse(status_code=207, content=response.model_dump(mode="json"))
    return response


@router.delete("/delete", response_model=DeleteResponse)
def delete_items(req: DeleteRequest):
    service = get_service()
    deleted = []
    failed = []

    for path in req.paths:
        try:
            service.delete_path(path, req.recursive)
            deleted.append(path)
        except Exception as e:
            failed.append({"path": path, "error": str(e)})

    if failed:
        return JSONResponse(
            status_code=207,
            content={
                "success": False,
                "message": f"Deleted {len(deleted)} of {len(req.paths)} items",
                "deleted": deleted,
                "failed": failed,
            },
        )

    return DeleteResponse(
        success=True,
        message=f"Successfully deleted {len(deleted)} items",
        deleted=deleted,
        failed=[],
    )


@router.post("/rename")
def rename_item(req: RenameRequest):
    service = get_service()
    try:
        # Check if destination is just a name or full path
        dest = req.destination
        if os.path.sep not in dest:
            dest = os.path.join(os.path.dirname(req.source), dest)

        new_path = service.rename_path(req.source, dest, req.overwrite)
        return {
            "success": True,
            "message": "Renamed successfully",
            "old_path": req.source,
            "new_path": new_path,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source not found")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Destination exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
def download_file(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Cannot download directory")

    filename = os.path.basename(path)
    return FileResponse(path, filename=filename, media_type="application/octet-stream")


# --- Clipboard ---


@router.post("/clipboard/copy")
def clipboard_copy(req: ClipboardCopyRequest):
    clipboard_store[req.session_id] = {
        "operation": "copy",
        "paths": req.paths,
        "timestamp": datetime.now(),
    }
    return {
        "success": True,
        "message": f"{len(req.paths)} items copied to clipboard",
        "operation": "copy",
        "items_count": len(req.paths),
        "session_id": req.session_id,
    }


@router.post("/clipboard/cut")
def clipboard_cut(req: ClipboardCopyRequest):
    clipboard_store[req.session_id] = {
        "operation": "cut",
        "paths": req.paths,
        "timestamp": datetime.now(),
    }
    return {
        "success": True,
        "message": f"{len(req.paths)} items cut to clipboard",
        "operation": "cut",
        "items_count": len(req.paths),
        "session_id": req.session_id,
    }


@router.post("/clipboard/paste", status_code=202)
def clipboard_paste(req: ClipboardPasteRequest, background_tasks: BackgroundTasks):
    session_data = clipboard_store.get(req.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Clipboard session not found")

    paths = session_data["paths"]
    op_type = "move" if session_data["operation"] == "cut" else "copy"

    manager = get_manager()
    op = manager.create_operation(op_type, OperationStatus.PENDING)
    op.source_paths = paths
    op.destination_path = req.destination
    manager.update_operation(op)

    background_tasks.add_task(
        perform_paste,
        op.id,
        paths,
        req.destination,
        req.conflict_resolution,
        req.rename_pattern,
    )

    # If cut, clear clipboard? Usually yes.
    if session_data["operation"] == "cut":
        del clipboard_store[req.session_id]

    return {
        "success": True,
        "message": "Paste operation started",
        "operation_id": op.id,
        "operation_type": op_type,
        "status": "pending",
        "total_items": len(paths),
    }


@router.get("/clipboard/status", response_model=ClipboardStatusResponse)
def clipboard_status(session_id: str):
    data = clipboard_store.get(session_id)
    if not data:
        return ClipboardStatusResponse(
            has_items=False,
            items_count=0,
            paths=[],
            total_size=0,
            total_size_human="0 B",
        )

    # Calculate size (optional, might be slow for many files)
    total_size = 0
    # For now skipping real size calc to avoid perf hit, just returning placeholder or calc if small list

    return ClipboardStatusResponse(
        has_items=True,
        operation=data["operation"],
        items_count=len(data["paths"]),
        paths=data["paths"],
        total_size=0,
        total_size_human="N/A",  # TODO: Implement size calc
    )


@router.delete("/clipboard/clear")
def clipboard_clear(session_id: str):
    if session_id in clipboard_store:
        del clipboard_store[session_id]
    return {"success": True, "message": "Clipboard cleared"}


# --- Bookmarks (Filesystem Locations) ---


@router.get("/bookmarks")
def list_bookmarks():
    manager = get_manager()
    locations = manager.get_locations()
    # Check existence
    result = []
    for loc in locations:
        loc.exists = os.path.exists(loc.path)
        result.append(loc)
    return {"success": True, "bookmarks": result, "total": len(result)}


@router.post("/bookmarks", status_code=201)
def create_bookmark(req: LocationCreateRequest):
    manager = get_manager()
    loc = manager.create_location(req.label, req.path, req.type, req.description)
    return {
        "success": True,
        "message": "Bookmark created successfully",
        "bookmark": loc,
    }


@router.put("/bookmarks/{bookmark_id}")
def update_bookmark(bookmark_id: int, req: LocationUpdateRequest):
    manager = get_manager()
    loc = manager.update_location(bookmark_id, req.label, req.path, req.description)
    if not loc:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {
        "success": True,
        "message": "Bookmark updated successfully",
        "bookmark": loc,
    }


@router.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: int):
    manager = get_manager()
    try:
        manager.delete_location(bookmark_id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return {"success": True, "message": "Bookmark deleted successfully"}


# --- USB ---


@router.get("/usb-devices")
def list_usb_devices():
    service = get_service()
    devices = service.get_usb_devices()
    return {"success": True, "devices": devices, "total_devices": len(devices)}


# --- Search ---


@router.post("/search", status_code=202)
def search_files(req: SearchRequest, background_tasks: BackgroundTasks):
    manager = get_manager()
    op = manager.create_operation(OperationType.SEARCH, OperationStatus.PENDING)
    op.source_paths = [req.path]  # Store root as source
    manager.update_operation(op)

    background_tasks.add_task(
        perform_search,
        op.id,
        req.path,
        req.pattern,
        req.use_regex,
        req.case_sensitive,
        req.type_filter,
        req.show_hidden,
    )

    return {
        "success": True,
        "message": "Search operation started",
        "operation_id": op.id,
        "operation_type": "search",
        "status": "pending",
    }


# --- Operations ---


@router.get("/operations/{operation_id}", response_model=OperationResponse)
def get_operation_status(operation_id: str):
    manager = get_manager()
    op = manager.get_operation(operation_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    return OperationResponse(operation=op)


@router.get("/operations")
def list_operations(
    status: Optional[str] = None,
    operation_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    manager = get_manager()
    # Filter not implemented in manager yet, just pagination
    # Doing in-memory filter or assume manager update later
    ops = manager.get_operations(limit=1000, offset=0)  # Fetch more then filter

    filtered = []
    for op in ops:
        if status and op.status != status:
            continue
        if operation_type and op.operation_type != operation_type:
            continue
        filtered.append(op)

    # paginate
    total = len(filtered)
    start = offset
    end = offset + limit
    sliced = filtered[start:end]

    return {
        "success": True,
        "operations": sliced,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/operations/{operation_id}/cancel", response_model=OperationResponse)
def cancel_operation(operation_id: str):
    manager = get_manager()
    op = manager.get_operation(operation_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")

    if op.status in {OperationStatus.COMPLETED, OperationStatus.FAILED}:
        return OperationResponse(operation=op)

    op.status = OperationStatus.CANCELLED
    op.error_message = op.error_message or "Operation cancelled"
    op.completed_at = datetime.utcnow()
    if isinstance(op.result, dict):
        result = dict(op.result)
        result["status"] = OperationStatus.CANCELLED
        if isinstance(result.get("files"), list):
            for item in result["files"]:
                if item.get("status") in {
                    OperationStatus.PENDING,
                    OperationStatus.IN_PROGRESS,
                }:
                    item["status"] = OperationStatus.CANCELLED
                    item["error_message"] = (
                        item.get("error_message") or "Operation cancelled"
                    )
        op.result = result

    manager.update_operation(op)
    refreshed = manager.get_operation(operation_id) or op
    return OperationResponse(operation=refreshed)


@router.delete("/operations/{operation_id}")
def delete_operation(operation_id: str):
    manager = get_manager()
    # If in progress, should cancel task?
    # Cancelling background tasks in FastAPI/Python threads is hard without specific mechanism.
    # For now just deleting record.
    manager.delete_operation(operation_id)
    return {"success": True, "message": "Operation cancelled/deleted successfully"}


# --- Config ---


@router.get("/config")
def get_explorer_config():
    manager = get_manager()
    config = manager.get_config()
    return {"success": True, "config": config}


@router.put("/config")
def update_explorer_config(req: ConfigUpdateRequest):
    manager = get_manager()
    if req.show_hidden_files is not None:
        manager.update_config("show_hidden_files", str(req.show_hidden_files).lower())
    if req.usb_mount_path:
        manager.update_config("usb_mount_path", req.usb_mount_path)
    if req.root_directory:
        manager.update_config("root_directory", req.root_directory)

    return {
        "success": True,
        "message": "Configuration updated successfully",
        "config": manager.get_config(),
    }
