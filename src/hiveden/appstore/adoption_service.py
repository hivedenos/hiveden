from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.request import Request, urlopen

from hiveden.appstore.catalog_service import AppCatalogService
from hiveden.appstore.compose_translator import parse_compose_yaml
from hiveden.docker.containers import DockerManager
from hiveden.docker.models import Container


@dataclass
class AppAdoptionResult:
    containers: List[Container]
    warnings: List[str] = field(default_factory=list)


class AppAdoptionService:
    def __init__(self):
        self.catalog = AppCatalogService()
        self.docker = DockerManager()

    def adopt_app(
        self,
        app_id: str,
        container_names_or_ids: List[str],
        replace_existing: bool = False,
        force: bool = False,
    ) -> AppAdoptionResult:
        app = self.catalog.get_app(app_id)
        if not app:
            raise ValueError(f"App '{app_id}' was not found in catalog")
        if not app.installable:
            raise ValueError(
                app.install_block_reason or f"App '{app.app_id}' cannot be installed"
            )
        if app.install_status in {"installing", "uninstalling"}:
            raise ValueError(f"App '{app.app_id}' is currently {app.install_status}")

        identifiers = [
            item.strip() for item in container_names_or_ids if item and item.strip()
        ]
        if not identifiers:
            raise ValueError("At least one container name or ID is required")

        warnings: List[str] = []
        expected_images = self._get_expected_images(app.compose_url, warnings)
        resolved: List[Container] = []
        seen_names: Set[str] = set()

        for identifier in identifiers:
            try:
                container = self.docker.get_container(identifier)
            except Exception as exc:
                raise ValueError(f"Container '{identifier}' was not found: {exc}")

            container_name = (container.Name or "").lstrip("/")
            if not container_name:
                raise ValueError(f"Container '{identifier}' does not have a valid name")
            if container_name in seen_names:
                continue

            self._validate_conflicts(
                app_id=app_id,
                container_name=container_name,
                force=force,
                warnings=warnings,
            )
            self._validate_image(
                app_id=app_id,
                container=container,
                expected_images=expected_images,
                force=force,
                warnings=warnings,
            )

            seen_names.add(container_name)
            resolved.append(container)

        if not resolved:
            raise ValueError("No valid containers were provided")

        if replace_existing:
            self.catalog.delete_resources_by_type(app.catalog_id, "container")
        else:
            for container in resolved:
                self.catalog.delete_resource(
                    app_id=app.catalog_id,
                    resource_type="container",
                    resource_name=container.Name,
                )

        for container in resolved:
            self.catalog.add_resource(
                app_id=app.catalog_id,
                resource_type="container",
                resource_name=container.Name,
                metadata={
                    "external": True,
                    "container_id": container.Id,
                    "image": container.Image,
                    "status": container.Status,
                },
            )

        self.catalog.set_installation_status(
            app_id=app.catalog_id,
            status="installed",
            installed_version=app.version,
            last_error=None,
        )

        return AppAdoptionResult(containers=resolved, warnings=warnings)

    def _validate_conflicts(
        self,
        app_id: str,
        container_name: str,
        force: bool,
        warnings: List[str],
    ):
        owners = self.catalog.list_container_resource_owners(
            container_name=container_name,
            exclude_app_id=app_id,
        )
        if not owners:
            return

        message = (
            f"Container '{container_name}' is already linked to app(s): "
            + ", ".join(sorted(owners))
        )
        if force:
            warnings.append(message)
            return
        raise ValueError(message + ". Retry with force=true to continue.")

    def _validate_image(
        self,
        app_id: str,
        container: Container,
        expected_images: Set[str],
        force: bool,
        warnings: List[str],
    ):
        if not expected_images:
            return

        container_image = self._normalize_image_ref(container.Image)
        if container_image in expected_images:
            return

        message = (
            f"Container '{container.Name}' uses image '{container.Image}', "
            f"which does not match expected images for app '{app_id}'"
        )
        if force:
            warnings.append(message)
            return
        raise ValueError(message + ". Retry with force=true to continue.")

    def _get_expected_images(
        self, compose_url: Optional[str], warnings: List[str]
    ) -> Set[str]:
        if not compose_url:
            return set()

        try:
            request = Request(
                compose_url, headers={"Accept": "text/yaml,text/plain,*/*"}
            )
            with urlopen(request, timeout=20) as response:
                content = response.read().decode("utf-8")
            compose_data = parse_compose_yaml(content)
            services = compose_data.get("services") or {}
            images: Set[str] = set()
            for spec in services.values():
                if not isinstance(spec, dict):
                    continue
                image = spec.get("image")
                normalized = self._normalize_image_ref(image)
                if normalized:
                    images.add(normalized)
            return images
        except Exception as exc:
            warnings.append(f"Failed to validate compose images: {exc}")
            return set()

    def _normalize_image_ref(self, image: Optional[str]) -> str:
        if not isinstance(image, str):
            return ""

        value = image.strip().lower()
        if not value:
            return ""

        without_digest = value.split("@", 1)[0]
        if "/" in without_digest and ":" in without_digest.rsplit("/", 1)[-1]:
            without_tag = without_digest.rsplit(":", 1)[0]
        elif "/" not in without_digest and ":" in without_digest:
            without_tag = without_digest.rsplit(":", 1)[0]
        else:
            without_tag = without_digest

        return without_tag
