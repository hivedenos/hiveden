from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.request import Request, urlopen

from hiveden.appstore.catalog_service import AppCatalogService
from hiveden.appstore.compose_translator import parse_compose_yaml
from hiveden.docker.containers import DockerManager
from hiveden.docker.models import Container


@dataclass
class AppAdoptionResult:
    containers: List[object]
    warnings: List[str] = field(default_factory=list)


@dataclass
class LinkedContainerReference:
    Id: str
    Name: str
    Image: Optional[str] = None
    Status: Optional[str] = None


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
        resolved: List[LinkedContainerReference] = []
        seen_names: Set[str] = set()

        for identifier in identifiers:
            container = self._resolve_container_reference(identifier)
            container_name = self._normalize_container_identifier(container.Name)
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
                    resource_name=container_name,
                )

        for container in resolved:
            container_name = self._normalize_container_identifier(container.Name)
            self.catalog.add_resource(
                app_id=app.catalog_id,
                resource_type="container",
                resource_name=container_name,
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

    def unlink_adopted_container(self, app_id: str, container_id: str) -> str:
        app = self.catalog.get_app(app_id)
        if not app:
            raise ValueError(f"App '{app_id}' was not found in catalog")
        if app.install_status in {"installing", "uninstalling"}:
            raise ValueError(f"App '{app.app_id}' is currently {app.install_status}")

        resource = self._find_linked_container_resource(app.catalog_id, container_id)
        if not resource:
            return ""
        if not self._is_external_resource(resource):
            raise ValueError(
                f"Container '{container_id}' was installed by app '{app.app_id}' and cannot be unlinked"
            )

        self.catalog.delete_resource(
            app_id=app.catalog_id,
            resource_type="container",
            resource_name=resource["resource_name"],
        )

        remaining_resources = self.catalog.list_resources(app.catalog_id)
        remaining_containers = [
            item
            for item in remaining_resources
            if item.get("resource_type") == "container"
        ]
        if not remaining_containers:
            self.catalog.set_installation_status(
                app_id=app.catalog_id,
                status="not_installed",
                installed_version=None,
                last_error=None,
            )

        return resource["resource_name"]

    def _resolve_container_reference(self, identifier: str) -> LinkedContainerReference:
        try:
            container = self.docker.get_container(identifier)
            return LinkedContainerReference(
                Id=container.Id,
                Name=self._normalize_container_identifier(container.Name),
                Image=container.Image,
                Status=container.Status,
            )
        except Exception:
            normalized_identifier = self._normalize_container_identifier(identifier)
            return LinkedContainerReference(
                Id=normalized_identifier,
                Name=normalized_identifier,
            )

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
        if not getattr(container, "Image", None):
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

    def _find_linked_container_resource(
        self, catalog_id: str, container_id: str
    ) -> Optional[dict]:
        normalized_identifier = self._normalize_container_identifier(container_id)
        for resource in self.catalog.list_resources(catalog_id):
            if resource.get("resource_type") != "container":
                continue
            metadata = resource.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}

            candidates = [
                resource.get("resource_name"),
                metadata.get("container_id"),
            ]
            normalized_candidates = {
                self._normalize_container_identifier(candidate)
                for candidate in candidates
                if isinstance(candidate, str) and candidate.strip()
            }
            if normalized_identifier in normalized_candidates:
                return resource
        return None

    def _normalize_container_identifier(self, value: Optional[str]) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lstrip("/")

    def _is_external_resource(self, resource: dict) -> bool:
        metadata = resource.get("metadata")
        if not isinstance(metadata, dict):
            return False
        return bool(metadata.get("external", False))
