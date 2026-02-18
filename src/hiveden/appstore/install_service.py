import hashlib
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen

from hiveden.appstore.catalog_service import AppCatalogService
from hiveden.appstore.compose_translator import (
    parse_compose_yaml,
    translate_compose_services,
)
from hiveden.docker.containers import DockerManager
from hiveden.jobs.manager import JobManager
from hiveden.pkgs.manager import get_package_manager


class AppInstallService:
    def __init__(self):
        self.catalog = AppCatalogService()
        self.docker = DockerManager()

    async def install_app(
        self,
        job_id: str,
        job_manager: JobManager,
        app_id: str,
        auto_install_prereqs: bool = False,
        env_overrides: Optional[Dict[str, str]] = None,
    ):
        app = self.catalog.get_app(app_id)
        if not app:
            raise ValueError(f"App '{app_id}' was not found in catalog")
        if app.install_status in {"installing", "uninstalling"}:
            raise ValueError(f"App '{app_id}' is currently {app.install_status}")

        self.catalog.set_installation_status(app_id, "installing", installed_version=app.version)
        await job_manager.log(job_id, f"Preparing installation for {app_id}")

        try:
            await self._validate_dependencies(job_id, job_manager, app, auto_install_prereqs)
            compose_content = self._download_text(app.compose_url)
            self._verify_compose_checksum(compose_content, app.compose_sha256)
            compose_data = parse_compose_yaml(compose_content)
            translated = translate_compose_services(
                app_id=app_id,
                compose_data=compose_data,
                env_overrides=env_overrides or {},
            )
            translated = self._sort_services_by_dependencies(translated)

            await job_manager.log(job_id, f"Installing {len(translated)} service(s)")
            for service in translated:
                await job_manager.log(
                    job_id,
                    f"Creating container {service['name']} from image {service['image']}",
                )
                container = self.docker.create_container(
                    name=service["name"],
                    image=service["image"],
                    command=service["command"],
                    dependencies=service["dependencies"],
                    env=service["env"],
                    ports=service["ports"],
                    mounts=service["mounts"],
                    devices=service["devices"],
                    labels=service["labels"],
                    privileged=service["privileged"],
                )
                self.catalog.add_resource(
                    app_id=app_id,
                    resource_type="container",
                    resource_name=container.name,
                    metadata={"image": service["image"]},
                )
                for app_dir in service["app_directories"]:
                    self.catalog.add_resource(
                        app_id=app_id,
                        resource_type="directory",
                        resource_name=app_dir,
                        metadata={"service": service["name"]},
                    )

            self.catalog.set_installation_status(
                app_id,
                "installed",
                installed_version=app.version,
            )
            await job_manager.log(job_id, f"App {app_id} installed successfully")
        except Exception as exc:
            self.catalog.set_installation_status(
                app_id,
                "failed",
                installed_version=app.version,
                last_error=str(exc),
            )
            raise

    async def _validate_dependencies(
        self,
        job_id: str,
        job_manager: JobManager,
        app: Any,
        auto_install_prereqs: bool,
    ):
        for dependency_app in app.dependencies_apps:
            dep = self.catalog.get_app(dependency_app)
            if not dep or not dep.installed:
                raise ValueError(
                    f"Missing app dependency '{dependency_app}' for '{app.app_id}'"
                )

        required_packages = app.dependencies_system_packages or []
        if not required_packages:
            return

        pm = get_package_manager()
        missing = [pkg for pkg in required_packages if not pm.is_installed(pkg)]
        if not missing:
            return
        if not auto_install_prereqs:
            raise ValueError(
                "Missing system package dependencies: "
                + ", ".join(missing)
                + ". Retry with auto_install_prereqs=true."
            )

        await job_manager.log(job_id, f"Installing system packages: {', '.join(missing)}")
        for pkg in missing:
            pm.install(pkg)
            await job_manager.log(job_id, f"Installed package: {pkg}")

    def _download_text(self, url: Optional[str]) -> str:
        if not url:
            raise ValueError("Catalog entry does not include compose_url")
        request = Request(url, headers={"Accept": "text/yaml,text/plain,*/*"})
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8")

    def _verify_compose_checksum(self, content: str, expected_sha256: Optional[str]):
        if not expected_sha256:
            return
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest != expected_sha256:
            raise ValueError("Compose checksum mismatch")

    def _sort_services_by_dependencies(self, services: list[dict]) -> list[dict]:
        by_name = {item["name"]: item for item in services}
        pending = set(by_name.keys())
        ordered: list[dict] = []

        while pending:
            progressed = False
            for name in list(pending):
                deps = by_name[name].get("dependencies") or []
                if all(dep not in pending for dep in deps):
                    ordered.append(by_name[name])
                    pending.remove(name)
                    progressed = True
            if not progressed:
                cycle = ", ".join(sorted(pending))
                raise ValueError(f"Cyclic or unresolved service dependencies: {cycle}")

        return ordered
