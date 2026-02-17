import os
import shutil
from typing import List

from docker import errors

from hiveden.appstore.catalog_service import AppCatalogService
from hiveden.docker.containers import DockerManager
from hiveden.jobs.manager import JobManager


class AppUninstallService:
    def __init__(self):
        self.catalog = AppCatalogService()
        self.docker = DockerManager()

    async def uninstall_app(
        self,
        job_id: str,
        job_manager: JobManager,
        app_id: str,
        delete_data: bool = False,
        delete_databases: bool = False,
        delete_dns: bool = False,
    ):
        app = self.catalog.get_app(app_id)
        if not app:
            raise ValueError(f"App '{app_id}' was not found in catalog")
        if app.install_status in {"installing", "uninstalling"}:
            raise ValueError(f"App '{app_id}' is currently {app.install_status}")
        if not app.installed:
            raise ValueError(f"App '{app_id}' is not installed")

        self.catalog.set_installation_status(app_id, "uninstalling", installed_version=app.version)
        await job_manager.log(job_id, f"Preparing uninstall for {app_id}")

        resources = self.catalog.list_resources(app_id)
        container_resources = [r for r in resources if r["resource_type"] == "container"]
        for resource in container_resources:
            name = resource["resource_name"]
            await job_manager.log(job_id, f"Removing container {name}")
            self._remove_container(name, delete_databases, delete_dns)

        if delete_data:
            app_root = self.docker._resolve_app_directory()
            directories = self._collect_directories(resources)
            for rel_path in directories:
                target = os.path.join(app_root, rel_path)
                if os.path.exists(target):
                    await job_manager.log(job_id, f"Deleting directory {target}")
                    shutil.rmtree(target, ignore_errors=True)

            app_dir = os.path.join(app_root, app_id)
            if os.path.exists(app_dir):
                await job_manager.log(job_id, f"Deleting app root {app_dir}")
                shutil.rmtree(app_dir, ignore_errors=True)

        self.catalog.delete_resources(app_id)
        self.catalog.set_installation_status(app_id, "not_installed", installed_version=None, last_error=None)
        await job_manager.log(job_id, f"App {app_id} uninstalled successfully")

    def _remove_container(self, container_name: str, delete_databases: bool, delete_dns: bool):
        try:
            c = self.docker.client.containers.get(container_name)
            if c.status == "running":
                c.stop()
            self.docker.remove_container(
                container_name,
                delete_database=delete_databases,
                delete_volumes=False,
                delete_dns=delete_dns,
            )
        except errors.NotFound:
            return

    def _collect_directories(self, resources: List[dict]) -> List[str]:
        result = []
        for resource in resources:
            if resource["resource_type"] != "directory":
                continue
            value = resource["resource_name"].strip("/")
            if value and value not in result:
                result.append(value)
        return result

