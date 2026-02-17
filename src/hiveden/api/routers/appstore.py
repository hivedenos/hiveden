import asyncio
import traceback
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.logger import logger

from hiveden.api.dtos import (
    AppDetail,
    AppDetailResponse,
    AppInstallRequest,
    AppInstallResponse,
    AppListResponse,
    AppSummary,
    AppSyncResponse,
    AppUninstallRequest,
)
from hiveden.appstore.catalog_client import CatalogClient
from hiveden.appstore.catalog_service import AppCatalogService
from hiveden.appstore.install_service import AppInstallService
from hiveden.appstore.uninstall_service import AppUninstallService
from hiveden.config.settings import config
from hiveden.jobs.manager import JobManager

router = APIRouter(prefix="/app-store", tags=["App Store"])


def _to_summary(entry) -> AppSummary:
    payload = {
        "app_id": entry.app_id,
        "title": entry.title,
        "version": entry.version,
        "tagline": entry.tagline,
        "description": entry.description,
        "category": entry.category,
        "icon": entry.icon,
        "icon_url": getattr(entry, "icon_url", None),
        "compose_url": getattr(entry, "compose_url", None),
        "image_urls": getattr(entry, "image_urls", []) or [],
        "dependencies": getattr(entry, "dependencies", []) or [],
        "repository_path": getattr(entry, "repository_path", None),
        "developer": entry.developer,
        "installed": entry.installed,
        "install_status": entry.install_status,
    }
    return AppSummary.model_validate(payload)


def _to_detail(entry) -> AppDetail:
    summary = _to_summary(entry)
    payload = summary.model_dump()
    payload.update(
        {
            "website": entry.website,
            "repo": entry.repo,
            "support": entry.support,
            "dependencies_apps": entry.dependencies_apps,
            "dependencies_system_packages": entry.dependencies_system_packages,
            "manifest_url": entry.manifest_url,
            "compose_url": entry.compose_url,
            "source": getattr(entry, "source", {}) or {},
            "install": getattr(entry, "install", {}) or {},
            "search": getattr(entry, "search", {}) or {},
            "dependencies": getattr(entry, "dependencies", []) or [],
            "source_updated_at": getattr(entry, "source_updated_at", None),
        }
    )
    return AppDetail.model_validate(payload)


@router.post("/sync", response_model=AppSyncResponse, status_code=202)
async def sync_catalog():
    if not config.appstore_index_url:
        raise HTTPException(
            status_code=400,
            detail="HIVEDEN_APPSTORE_INDEX_URL is not configured",
        )

    job_manager = JobManager()
    job_id = job_manager.create_external_job("appstore.sync")

    async def worker(current_job_id: str, manager: JobManager):
        await manager.log(current_job_id, "Fetching app catalog index")
        client = CatalogClient(timeout_seconds=config.appstore_http_timeout_seconds)
        payload = client.fetch_catalog(config.appstore_index_url)
        apps = payload.get("apps", [])
        service = AppCatalogService()
        result = service.upsert_catalog(apps)
        await manager.log(
            current_job_id,
            f"Catalog sync completed: {result.upserted}/{result.total} entries updated",
        )

    asyncio.create_task(job_manager.run_external_job(job_id, worker))
    return AppSyncResponse.model_validate(
        {"message": "Catalog sync started", "data": {"job_id": job_id}}
    )


@router.get("/apps", response_model=AppListResponse)
def list_apps(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Category filter"),
    installed: Optional[bool] = Query(None, description="Filter by install state"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    try:
        service = AppCatalogService()
        entries = service.list_apps(
            q=q, category=category, installed=installed, limit=limit, offset=offset
        )
        return AppListResponse(data=[_to_summary(entry) for entry in entries])
    except Exception as exc:
        logger.error(
            "Error listing app store entries: %s\n%s", exc, traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/installed", response_model=AppListResponse)
def list_installed_apps():
    try:
        service = AppCatalogService()
        entries = service.list_installed_apps()
        return AppListResponse(data=[_to_summary(entry) for entry in entries])
    except Exception as exc:
        logger.error(
            "Error listing installed app store entries: %s\n%s",
            exc,
            traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/apps/{app_id}", response_model=AppDetailResponse)
def get_app_detail(app_id: str):
    service = AppCatalogService()
    entry = service.get_app(app_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    return AppDetailResponse(data=_to_detail(entry))


@router.post(
    "/apps/{app_id}/install", response_model=AppInstallResponse, status_code=202
)
async def install_app(app_id: str, payload: AppInstallRequest):
    service = AppCatalogService()
    app = service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    if app.install_status in {"installing", "uninstalling"}:
        raise HTTPException(
            status_code=409, detail=f"App '{app_id}' is currently {app.install_status}"
        )

    job_manager = JobManager()
    job_id = job_manager.create_external_job(f"appstore.install:{app_id}")
    installer = AppInstallService()

    async def worker(current_job_id: str, manager: JobManager):
        await installer.install_app(
            job_id=current_job_id,
            job_manager=manager,
            app_id=app_id,
            auto_install_prereqs=payload.auto_install_prereqs,
            env_overrides=payload.env_overrides,
        )

    asyncio.create_task(job_manager.run_external_job(job_id, worker))
    return AppInstallResponse.model_validate(
        {
            "message": f"Install started for {app_id}",
            "data": {"job_id": job_id},
        }
    )


@router.post(
    "/apps/{app_id}/uninstall", response_model=AppInstallResponse, status_code=202
)
async def uninstall_app(app_id: str, payload: AppUninstallRequest):
    service = AppCatalogService()
    app = service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    if app.install_status in {"installing", "uninstalling"}:
        raise HTTPException(
            status_code=409, detail=f"App '{app_id}' is currently {app.install_status}"
        )

    job_manager = JobManager()
    job_id = job_manager.create_external_job(f"appstore.uninstall:{app_id}")
    uninstaller = AppUninstallService()

    async def worker(current_job_id: str, manager: JobManager):
        await uninstaller.uninstall_app(
            job_id=current_job_id,
            job_manager=manager,
            app_id=app_id,
            delete_data=payload.delete_data,
            delete_databases=payload.delete_databases,
            delete_dns=payload.delete_dns,
        )

    asyncio.create_task(job_manager.run_external_job(job_id, worker))
    return AppInstallResponse.model_validate(
        {
            "message": f"Uninstall started for {app_id}",
            "data": {"job_id": job_id},
        }
    )
