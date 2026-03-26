import asyncio
import traceback
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.logger import logger

from hiveden.api.dtos import (
    AppCacheClearRequest,
    AppCacheClearResponse,
    AppAdoptRequest,
    AppAdoptResponse,
    AppDetail,
    AppDetailResponse,
    AppInstalledContainer,
    AppInstallRequest,
    AppInstallResponse,
    AppListResponse,
    AppPromotionRequestCreate,
    AppPromotionRequestInfo,
    AppPromotionRequestResponse,
    AppSummary,
    SuccessResponse,
    AppSyncResponse,
    AppUninstallRequest,
)
from hiveden.appstore.adoption_service import AppAdoptionService
from hiveden.appstore.catalog_client import CatalogClient
from hiveden.appstore.catalog_service import AppCatalogService
from hiveden.appstore.install_service import AppInstallService
from hiveden.appstore.uninstall_service import AppUninstallService
from hiveden.config.settings import config
from hiveden.docker.containers import DockerManager
from hiveden.jobs.manager import JobManager
from hiveden.services.logs import LogService

router = APIRouter(prefix="/app-store", tags=["App Store"])
APPSTORE_LOG_MODULE = "appstore"


def _appstore_log_info(action: str, message: str, metadata: Optional[dict] = None):
    LogService().info(
        actor="system",
        action=action,
        message=message,
        metadata=metadata or {},
        module=APPSTORE_LOG_MODULE,
    )


def _appstore_log_error(
    action: str, message: str, exc: Exception, metadata: Optional[dict] = None
):
    LogService().error(
        actor="system",
        action=action,
        message=message,
        error_details=str(exc),
        metadata=metadata or {},
        module=APPSTORE_LOG_MODULE,
    )


def _to_summary(entry) -> AppSummary:
    payload = {
        "catalog_id": entry.catalog_id,
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
        "channel": getattr(entry, "channel", "stable"),
        "channel_label": getattr(entry, "channel_label", None),
        "risk_level": getattr(entry, "risk_level", None),
        "support_tier": getattr(entry, "support_tier", None),
        "origin_channel": getattr(entry, "origin_channel", None),
        "promotion_status": getattr(entry, "promotion_status", None),
        "installed": entry.installed,
        "install_status": entry.install_status,
        "installable": getattr(entry, "installable", True),
        "install_block_reason": getattr(entry, "install_block_reason", None),
        "promotion_request_status": getattr(entry, "promotion_request_status", None),
    }
    return AppSummary.model_validate(payload)


def _to_detail(entry) -> AppDetail:
    return _to_detail_with_containers(entry, [])


def _normalize_container_resource_name(resource_name: Optional[str]) -> str:
    if not isinstance(resource_name, str):
        return ""
    return resource_name.lstrip("/")


def _to_installed_container(resource: dict) -> Optional[AppInstalledContainer]:
    if resource.get("resource_type") != "container":
        return None

    metadata = resource.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    container_id = metadata.get("container_id") or resource.get("resource_name")
    container_name = _normalize_container_resource_name(resource.get("resource_name"))
    if not container_id or not container_name:
        return None

    return AppInstalledContainer.model_validate(
        {
            "container_id": container_id,
            "container_name": container_name,
            "image": metadata.get("image"),
            "status": metadata.get("status"),
            "external": bool(metadata.get("external", False)),
            "can_unlink": bool(metadata.get("external", False)),
        }
    )


def _enrich_installed_container(
    container: AppInstalledContainer, docker_manager: DockerManager
) -> AppInstalledContainer:
    lookup_keys = [container.container_id]
    if container.container_name and container.container_name not in lookup_keys:
        lookup_keys.append(container.container_name)

    for lookup_key in lookup_keys:
        try:
            docker_container = docker_manager.get_container(lookup_key)
            return AppInstalledContainer.model_validate(
                {
                    "container_id": docker_container.Id,
                    "container_name": _normalize_container_resource_name(
                        docker_container.Name
                    ),
                    "image": docker_container.Image or container.image,
                    "status": docker_container.Status or container.status,
                    "external": container.external,
                    "can_unlink": container.can_unlink,
                }
            )
        except Exception:
            continue

    return container


def _resolve_installed_containers(resources: list[dict]) -> list[AppInstalledContainer]:
    containers = []
    for resource in resources:
        container = _to_installed_container(resource)
        if container:
            containers.append(container)

    if not containers:
        return []

    docker_manager = DockerManager()
    return [
        _enrich_installed_container(container, docker_manager)
        for container in containers
    ]


def _to_detail_with_containers(entry, resources: list[dict]) -> AppDetail:
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
            "installed_containers": _resolve_installed_containers(resources),
        }
    )
    return AppDetail.model_validate(payload)


def _to_adopted_container(container) -> dict:
    return {
        "container_id": container.Id,
        "container_name": container.Name.lstrip("/"),
        "image": container.Image,
        "status": container.Status,
        "external": True,
    }


def _build_promotion_request_info(app, payload: AppPromotionRequestCreate):
    target_channel = (payload.target_channel or "edge").strip().lower()
    if target_channel not in {"stable", "beta", "edge"}:
        raise HTTPException(
            status_code=400,
            detail="target_channel must be one of: stable, beta, edge",
        )

    repo_url = "https://github.com/hivedenos/hivedenos-apps"
    source = getattr(app, "source", {}) or {}
    source_id = source.get("id") if isinstance(source, dict) else None
    suggested_title = f"Promote app: {app.app_id} from incubator to {target_channel}"
    requested_by = payload.requested_by or ""
    suggested_body = "\n".join(
        [
            "## Promotion request",
            f"- App ID: `{app.app_id}`",
            f"- Catalog ID: `{app.catalog_id}`",
            f"- Current channel: `{app.channel}`",
            f"- Requested channel: `{target_channel}`",
            f"- Repository path: `{getattr(app, 'repository_path', None) or 'unknown'}`",
            f"- Source ID: `{source_id or 'unknown'}`",
            f"- Developer: `{getattr(app, 'developer', None) or 'unknown'}`",
            f"- Requested by: `{requested_by or 'anonymous'}`",
            "",
            "### Reason",
            payload.reason or "Please review this incubator app for promotion.",
            "",
            "### Notes",
            "Incubator apps are discovery-only in Hiveden and must not be installed directly.",
            "Promotion requires a GitHub issue or, preferably, a pull request against hivedenos-apps.",
        ]
    )
    issue_query = urlencode({"title": suggested_title, "body": suggested_body})
    return AppPromotionRequestInfo.model_validate(
        {
            "catalog_id": app.catalog_id,
            "app_id": app.app_id,
            "channel": app.channel,
            "target_channel": target_channel,
            "github_repo_url": repo_url,
            "github_issue_url": f"{repo_url}/issues/new?{issue_query}",
            "github_pulls_url": f"{repo_url}/pulls",
            "suggested_title": suggested_title,
            "suggested_body": suggested_body,
            "reason": payload.reason,
            "requested_by": payload.requested_by,
        }
    )


def _catalog_apps_from_payload(payload: dict) -> list[dict]:
    apps_by_channel = payload.get("apps_by_channel")
    if not isinstance(apps_by_channel, dict):
        return payload.get("apps", []) or []

    catalog_apps = []
    for channel, entries in apps_by_channel.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized_entry = dict(entry)
            normalized_entry.setdefault("channel", channel)
            catalog_apps.append(normalized_entry)
    return catalog_apps


@router.post("/sync", response_model=AppSyncResponse, status_code=202)
async def sync_catalog():
    if not config.appstore_index_url:
        raise HTTPException(
            status_code=400,
            detail="HIVEDEN_APPSTORE_INDEX_URL is not configured",
        )

    _appstore_log_info(
        action="sync_catalog",
        message="App store catalog sync requested",
        metadata={"index_url": config.appstore_index_url},
    )

    job_manager = JobManager()
    job_id = job_manager.create_external_job("appstore.sync")

    async def worker(current_job_id: str, manager: JobManager):
        try:
            await manager.log(current_job_id, "Fetching app catalog index")
            client = CatalogClient(timeout_seconds=config.appstore_http_timeout_seconds)
            payload = client.fetch_catalog(config.appstore_index_url)
            apps = _catalog_apps_from_payload(payload)
            service = AppCatalogService()
            result = service.upsert_catalog(apps)
            _appstore_log_info(
                action="sync_catalog",
                message="App store catalog sync completed",
                metadata={"total": result.total, "upserted": result.upserted},
            )
            await manager.log(
                current_job_id,
                f"Catalog sync completed: {result.upserted}/{result.total} entries updated",
            )
        except Exception as exc:
            _appstore_log_error(
                action="sync_catalog",
                message="App store catalog sync failed",
                exc=exc,
                metadata={"index_url": config.appstore_index_url},
            )
            raise

    asyncio.create_task(job_manager.run_external_job(job_id, worker))
    return AppSyncResponse.model_validate(
        {"message": "Catalog sync started", "data": {"job_id": job_id}}
    )


@router.get("/apps", response_model=AppListResponse)
def list_apps(
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Category filter"),
    channel: Optional[str] = Query(None, description="Channel filter"),
    installed: Optional[bool] = Query(None, description="Filter by install state"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    try:
        _appstore_log_info(
            action="refresh_appstore",
            message="App store catalog refreshed",
            metadata={
                "query": q,
                "category": category,
                "channel": channel,
                "installed": installed,
                "limit": limit,
                "offset": offset,
            },
        )
        service = AppCatalogService()
        entries = service.list_apps(
            q=q,
            category=category,
            channel=channel,
            installed=installed,
            limit=limit,
            offset=offset,
        )
        return AppListResponse(data=[_to_summary(entry) for entry in entries])
    except Exception as exc:
        _appstore_log_error(
            action="refresh_appstore",
            message="App store refresh failed",
            exc=exc,
            metadata={"query": q, "category": category, "channel": channel},
        )
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
    resources = service.list_resources(entry.catalog_id) if entry.installed else []
    return AppDetailResponse(data=_to_detail_with_containers(entry, resources))


@router.post(
    "/apps/{app_id}/install", response_model=AppInstallResponse, status_code=202
)
async def install_app(app_id: str, payload: AppInstallRequest):
    service = AppCatalogService()
    app = service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    if not app.installable:
        raise HTTPException(status_code=409, detail=app.install_block_reason)
    if app.install_status in {"installing", "uninstalling"}:
        raise HTTPException(
            status_code=409, detail=f"App '{app_id}' is currently {app.install_status}"
        )

    _appstore_log_info(
        action="install_app",
        message=f"App install requested for {app.app_id}",
        metadata={"catalog_id": app.catalog_id, "app_id": app.app_id},
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
    if not app.installable:
        raise HTTPException(status_code=409, detail=app.install_block_reason)
    if app.install_status in {"installing", "uninstalling"}:
        raise HTTPException(
            status_code=409, detail=f"App '{app_id}' is currently {app.install_status}"
        )

    _appstore_log_info(
        action="uninstall_app",
        message=f"App uninstall requested for {app.app_id}",
        metadata={"catalog_id": app.catalog_id, "app_id": app.app_id},
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


@router.post("/apps/{app_id}/adopt", response_model=AppAdoptResponse)
def adopt_existing_app_containers(app_id: str, payload: AppAdoptRequest):
    service = AppCatalogService()
    app = service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    if not app.installable:
        raise HTTPException(status_code=409, detail=app.install_block_reason)
    if app.install_status in {"installing", "uninstalling"}:
        raise HTTPException(
            status_code=409, detail=f"App '{app_id}' is currently {app.install_status}"
        )
    if not payload.container_names_or_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one container name or ID is required",
        )

    adopter = AppAdoptionService()
    try:
        result = adopter.adopt_app(
            app_id=app_id,
            container_names_or_ids=payload.container_names_or_ids,
            replace_existing=payload.replace_existing,
            force=payload.force,
        )
        refreshed = service.get_app(app_id) or app
        _appstore_log_info(
            action="link_app",
            message=f"App linked to existing containers for {app.app_id}",
            metadata={
                "catalog_id": app.catalog_id,
                "app_id": app.app_id,
                "containers": payload.container_names_or_ids,
            },
        )
        return AppAdoptResponse.model_validate(
            {
                "message": f"App {app_id} linked to existing container(s)",
                "data": {
                    "app": _to_summary(refreshed).model_dump(),
                    "containers": [
                        _to_adopted_container(container)
                        for container in result.containers
                    ],
                    "warnings": result.warnings,
                },
            }
        )
    except ValueError as exc:
        _appstore_log_error(
            action="link_app",
            message=f"App link failed for {app_id}",
            exc=exc,
            metadata={"app_id": app_id, "containers": payload.container_names_or_ids},
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        _appstore_log_error(
            action="link_app",
            message=f"App link failed for {app_id}",
            exc=exc,
            metadata={"app_id": app_id, "containers": payload.container_names_or_ids},
        )
        logger.error(
            "Error linking existing containers for app %s: %s\n%s",
            app_id,
            exc,
            traceback.format_exc(),
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete(
    "/apps/{app_id}/containers/{container_id}", response_model=SuccessResponse
)
def unlink_adopted_app_container(app_id: str, container_id: str):
    service = AppCatalogService()
    app = service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")

    adoption_service = AppAdoptionService()
    try:
        resource_name = adoption_service.unlink_adopted_container(app_id, container_id)
        _appstore_log_info(
            action="unlink_app_container",
            message=f"Unlinked adopted container from {app.app_id}",
            metadata={
                "catalog_id": app.catalog_id,
                "app_id": app.app_id,
                "container_id": container_id,
                "resource_name": resource_name,
            },
        )
        return SuccessResponse(
            message=f"Container '{resource_name.lstrip('/')}' unlinked from app '{app_id}'"
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 400
        if "cannot be unlinked" in detail:
            status_code = 409
        elif "not linked to app" in detail:
            status_code = 404
        elif "currently" in detail or "not installed" in detail:
            status_code = 409
        raise HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/apps/{app_id}/promotion-request", response_model=AppPromotionRequestResponse
)
def request_app_promotion(app_id: str, payload: AppPromotionRequestCreate):
    service = AppCatalogService()
    app = service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
    if app.channel != "incubator":
        raise HTTPException(
            status_code=400,
            detail="Promotion requests are only supported for incubator apps",
        )

    request_info = _build_promotion_request_info(app, payload)
    return AppPromotionRequestResponse.model_validate(
        {
            "message": "Use GitHub to open an issue or submit a pull request for promotion",
            "data": request_info,
        }
    )


@router.post("/cache/clear", response_model=AppCacheClearResponse)
async def clear_catalog_cache(payload: AppCacheClearRequest):
    service = AppCatalogService()
    result = service.clear_catalog_cache()
    _appstore_log_info(
        action="clear_cache",
        message="App store cache cleared",
        metadata={
            "cleared_entries": result.cleared_entries,
            "sync_after_clear": payload.sync_after_clear,
        },
    )

    response_payload = {
        "message": "App store cache cleared",
        "data": {"cleared_entries": result.cleared_entries, "job_id": None},
    }

    if not payload.sync_after_clear:
        return AppCacheClearResponse.model_validate(response_payload)

    if not config.appstore_index_url:
        raise HTTPException(
            status_code=400,
            detail="HIVEDEN_APPSTORE_INDEX_URL is not configured",
        )

    job_manager = JobManager()
    job_id = job_manager.create_external_job("appstore.sync")

    async def worker(current_job_id: str, manager: JobManager):
        try:
            await manager.log(current_job_id, "Fetching app catalog index")
            client = CatalogClient(timeout_seconds=config.appstore_http_timeout_seconds)
            sync_payload = client.fetch_catalog(config.appstore_index_url)
            apps = _catalog_apps_from_payload(sync_payload)
            sync_result = service.upsert_catalog(apps)
            _appstore_log_info(
                action="sync_catalog",
                message="App store catalog sync completed after cache clear",
                metadata={"total": sync_result.total, "upserted": sync_result.upserted},
            )
            await manager.log(
                current_job_id,
                "Catalog sync completed: "
                f"{sync_result.upserted}/{sync_result.total} entries updated",
            )
        except Exception as exc:
            _appstore_log_error(
                action="sync_catalog",
                message="App store catalog sync after cache clear failed",
                exc=exc,
                metadata={"index_url": config.appstore_index_url},
            )
            raise

    asyncio.create_task(job_manager.run_external_job(job_id, worker))
    response_payload["message"] = "App store cache cleared and sync started"
    response_payload["data"]["job_id"] = job_id
    return AppCacheClearResponse.model_validate(response_payload)
