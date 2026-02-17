from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json

from hiveden.appstore.models import AppCatalogEntry, CatalogSyncResult
from hiveden.db.session import get_db_manager


CATALOG_RAW_BASE_URL = "https://raw.githubusercontent.com/hivedenos/hivedenos-apps/main"


class AppCatalogService:
    def __init__(self):
        self.db = get_db_manager()

    def upsert_catalog(self, apps: List[Dict[str, Any]]) -> CatalogSyncResult:
        if not apps:
            return CatalogSyncResult(total=0, upserted=0)

        conn = self.db.get_connection()
        upserted = 0
        try:
            cursor = conn.cursor()
            for app in apps:
                entry = self._normalize_app_entry(app)
                cursor.execute(
                    """
                    INSERT INTO app_catalog_entries (
                        app_id, title, version, tagline, description, category, icon,
                        developer, website, repo, support, dependencies_apps,
                        dependencies_system_packages, manifest_url, compose_url,
                        compose_sha256, repository_path, icon_url, image_urls,
                        source, install, search, dependencies, source_updated_at,
                        raw_manifest, updated_at
                    ) VALUES (
                        %(app_id)s, %(title)s, %(version)s, %(tagline)s, %(description)s, %(category)s, %(icon)s,
                        %(developer)s, %(website)s, %(repo)s, %(support)s, %(dependencies_apps)s,
                        %(dependencies_system_packages)s, %(manifest_url)s, %(compose_url)s,
                        %(compose_sha256)s, %(repository_path)s, %(icon_url)s,
                        %(image_urls)s, %(source)s, %(install)s, %(search)s,
                        %(dependencies)s, %(source_updated_at)s, %(raw_manifest)s,
                        CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (app_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        version = EXCLUDED.version,
                        tagline = EXCLUDED.tagline,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        icon = EXCLUDED.icon,
                        developer = EXCLUDED.developer,
                        website = EXCLUDED.website,
                        repo = EXCLUDED.repo,
                        support = EXCLUDED.support,
                        dependencies_apps = EXCLUDED.dependencies_apps,
                        dependencies_system_packages = EXCLUDED.dependencies_system_packages,
                        manifest_url = EXCLUDED.manifest_url,
                        compose_url = EXCLUDED.compose_url,
                        compose_sha256 = EXCLUDED.compose_sha256,
                        repository_path = EXCLUDED.repository_path,
                        icon_url = EXCLUDED.icon_url,
                        image_urls = EXCLUDED.image_urls,
                        source = EXCLUDED.source,
                        install = EXCLUDED.install,
                        search = EXCLUDED.search,
                        dependencies = EXCLUDED.dependencies,
                        source_updated_at = EXCLUDED.source_updated_at,
                        raw_manifest = EXCLUDED.raw_manifest,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    entry,
                )
                upserted += 1
            conn.commit()
            return CatalogSyncResult(total=len(apps), upserted=upserted)
        finally:
            conn.close()

    def list_apps(
        self,
        q: Optional[str] = None,
        category: Optional[str] = None,
        installed: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AppCatalogEntry]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            filters = []
            params: List[Any] = []

            if q:
                like = f"%{q}%"
                filters.append(
                    "(c.app_id ILIKE %s OR c.title ILIKE %s OR COALESCE(c.tagline, '') ILIKE %s OR COALESCE(c.description, '') ILIKE %s OR COALESCE(c.developer, '') ILIKE %s)"
                )
                params.extend([like, like, like, like, like])
            if category:
                filters.append("c.category = %s")
                params.append(category)
            if installed is True:
                filters.append("COALESCE(i.status, 'not_installed') = 'installed'")
            elif installed is False:
                filters.append("COALESCE(i.status, 'not_installed') <> 'installed'")

            where = f"WHERE {' AND '.join(filters)}" if filters else ""
            params.extend([limit, offset])
            query = f"""
                SELECT c.*, i.status AS install_status
                FROM app_catalog_entries c
                LEFT JOIN app_installations i ON i.app_id = c.app_id
                {where}
                ORDER BY c.title ASC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [self._row_to_entry(dict(row)) for row in rows]
        finally:
            conn.close()

    def get_app(self, app_id: str) -> Optional[AppCatalogEntry]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.*, i.status AS install_status
                FROM app_catalog_entries c
                LEFT JOIN app_installations i ON i.app_id = c.app_id
                WHERE c.app_id = %s
                """,
                (app_id,),
            )
            row = cursor.fetchone()
            return self._row_to_entry(dict(row)) if row else None
        finally:
            conn.close()

    def list_installed_apps(self) -> List[AppCatalogEntry]:
        return self.list_apps(installed=True, limit=500, offset=0)

    def set_installation_status(
        self,
        app_id: str,
        status: str,
        installed_version: Optional[str] = None,
        last_error: Optional[str] = None,
    ):
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO app_installations (app_id, installed_version, status, last_error, installed_at, updated_at)
                VALUES (%s, %s, %s, %s, CASE WHEN %s = 'installed' THEN CURRENT_TIMESTAMP ELSE NULL END, CURRENT_TIMESTAMP)
                ON CONFLICT (app_id) DO UPDATE SET
                    installed_version = EXCLUDED.installed_version,
                    status = EXCLUDED.status,
                    last_error = EXCLUDED.last_error,
                    installed_at = CASE WHEN EXCLUDED.status = 'installed' THEN CURRENT_TIMESTAMP ELSE app_installations.installed_at END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (app_id, installed_version, status, last_error, status),
            )
            conn.commit()
        finally:
            conn.close()

    def list_resources(self, app_id: str) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM app_install_resources WHERE app_id = %s ORDER BY id DESC",
                (app_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def add_resource(
        self,
        app_id: str,
        resource_type: str,
        resource_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO app_install_resources (app_id, resource_type, resource_name, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (app_id, resource_type, resource_name, Json(metadata or {})),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_resources(self, app_id: str):
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM app_install_resources WHERE app_id = %s", (app_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def _row_to_entry(self, row: Dict[str, Any]) -> AppCatalogEntry:
        install_status = row.get("install_status") or "not_installed"
        row_dependencies_apps = row.get("dependencies_apps") or []
        row_dependencies_system_packages = row.get("dependencies_system_packages") or []
        row_dependencies = row.get("dependencies") or []
        if not row_dependencies:
            row_dependencies = [
                *[item for item in row_dependencies_apps if isinstance(item, str)],
                *[
                    item
                    for item in row_dependencies_system_packages
                    if isinstance(item, str)
                ],
            ]

        source_updated_at = row.get("source_updated_at")
        source_updated_at_value = None
        if isinstance(source_updated_at, datetime):
            source_updated_at_value = source_updated_at.isoformat()

        row_source = row.get("source")
        if not isinstance(row_source, dict):
            row_source = {}

        row_icon_url = self._resolve_asset_url(
            value=row.get("icon_url") or row.get("icon"),
            repository_path=row.get("repository_path"),
            app_id=row.get("app_id"),
        )
        row_install = row.get("install")
        if not isinstance(row_install, dict):
            row_install = {}
        row_compose_url = self._resolve_repository_file_url(
            value=row.get("compose_url"),
            repository_path=row.get("repository_path"),
            app_id=row.get("app_id"),
            file_name="docker-compose.yml",
        )
        if not row_compose_url:
            row_compose_url = self._resolve_install_file_url(
                install=row_install,
                repository_path=row.get("repository_path"),
                app_id=row.get("app_id"),
                file_suffix="docker-compose.yml",
            )

        row_manifest_url = self._resolve_repository_file_url(
            value=row.get("manifest_url"),
            repository_path=row.get("repository_path"),
            app_id=row.get("app_id"),
            file_name="umbrel-app.yml",
        )
        if not row_manifest_url:
            row_manifest_url = self._resolve_install_file_url(
                install=row_install,
                repository_path=row.get("repository_path"),
                app_id=row.get("app_id"),
                file_suffix="umbrel-app.yml",
            )

        row_image_urls: List[str] = []
        for image_url in row.get("image_urls") or []:
            resolved_url = self._resolve_asset_url(
                value=image_url,
                repository_path=row.get("repository_path"),
                app_id=row.get("app_id"),
            )
            if resolved_url:
                row_image_urls.append(resolved_url)

        payload = {
            "app_id": row["app_id"],
            "title": row["title"],
            "version": row.get("version"),
            "tagline": row.get("tagline"),
            "description": row.get("description"),
            "category": row.get("category"),
            "icon": row_icon_url,
            "developer": row.get("developer"),
            "website": row.get("website"),
            "repo": row.get("repo"),
            "support": row.get("support"),
            "dependencies_apps": row_dependencies_apps,
            "dependencies_system_packages": row_dependencies_system_packages,
            "manifest_url": row_manifest_url,
            "compose_url": row_compose_url,
            "compose_sha256": row.get("compose_sha256"),
            "repository_path": row.get("repository_path"),
            "icon_url": row_icon_url,
            "image_urls": row_image_urls,
            "source": row_source,
            "install": row_install,
            "search": row.get("search") or {},
            "dependencies": row_dependencies,
            "source_updated_at": source_updated_at_value,
            "raw_manifest": row.get("raw_manifest") or {},
            "installed": install_status == "installed",
            "install_status": install_status,
        }
        return AppCatalogEntry.model_validate(payload)

    def _normalize_app_entry(self, app: Dict[str, Any]) -> Dict[str, Any]:
        legacy_dependencies = app.get("dependencies", {}) or {}
        if not isinstance(legacy_dependencies, dict):
            legacy_dependencies = {}

        source = app.get("source") or {}
        install = app.get("install") or {}
        search = app.get("search") or {}
        image_urls = app.get("image_urls") or []
        dependencies = app.get("dependencies") or []

        if not isinstance(source, dict):
            source = {}
        if not isinstance(install, dict):
            install = {}
        if not isinstance(search, dict):
            search = {}
        if not isinstance(image_urls, list):
            image_urls = []
        if not isinstance(dependencies, list):
            dependencies = []

        legacy_app_dependencies = [
            item
            for item in legacy_dependencies.get("apps", [])
            if isinstance(item, str)
        ]
        legacy_system_dependencies = [
            item
            for item in legacy_dependencies.get("system_packages", [])
            if isinstance(item, str)
        ]
        normalized_dependencies = [
            item for item in dependencies if isinstance(item, str)
        ]
        if not normalized_dependencies:
            normalized_dependencies = [
                *legacy_app_dependencies,
                *legacy_system_dependencies,
            ]

        app_id = app.get("id") or app.get("app_id")
        if not app_id:
            raise ValueError("Catalog app entry must include 'id'")
        repository_path = app.get("repository_path")

        compose_url = self._resolve_repository_file_url(
            value=app.get("compose_url"),
            repository_path=repository_path,
            app_id=app_id,
            file_name="docker-compose.yml",
        )
        manifest_url = self._resolve_repository_file_url(
            value=app.get("manifest_url"),
            repository_path=repository_path,
            app_id=app_id,
            file_name="umbrel-app.yml",
        )

        if not compose_url:
            compose_url = self._resolve_install_file_url(
                install=install,
                repository_path=repository_path,
                app_id=app_id,
                file_suffix="docker-compose.yml",
            )
        if not manifest_url:
            manifest_url = self._resolve_install_file_url(
                install=install,
                repository_path=repository_path,
                app_id=app_id,
                file_suffix="umbrel-app.yml",
            )

        icon_url = self._resolve_asset_url(
            value=app.get("icon_url") or app.get("icon"),
            repository_path=repository_path,
            app_id=app_id,
        )
        normalized_image_urls: List[str] = []
        for image_url in image_urls:
            resolved_url = self._resolve_asset_url(
                value=image_url,
                repository_path=repository_path,
                app_id=app_id,
            )
            if resolved_url:
                normalized_image_urls.append(resolved_url)

        return {
            "app_id": app_id,
            "title": app.get("name") or app.get("title") or app_id,
            "version": app.get("version"),
            "tagline": app.get("tagline"),
            "description": app.get("description"),
            "category": self._extract_category(app, search),
            "icon": icon_url,
            "developer": app.get("developer"),
            "website": app.get("website"),
            "repo": app.get("repo"),
            "support": app.get("support"),
            "dependencies_apps": legacy_app_dependencies,
            "dependencies_system_packages": legacy_system_dependencies,
            "manifest_url": manifest_url,
            "compose_url": compose_url,
            "compose_sha256": (app.get("sha256") or {}).get("compose"),
            "repository_path": repository_path,
            "icon_url": icon_url,
            "image_urls": normalized_image_urls,
            "source": Json(source),
            "install": Json(install),
            "search": Json(search),
            "dependencies": normalized_dependencies,
            "source_updated_at": self._parse_source_updated_at(app.get("updated_at")),
            "raw_manifest": Json(app.get("raw_manifest") or app),
        }

    def _extract_category(
        self, app: Dict[str, Any], search: Dict[str, Any]
    ) -> Optional[str]:
        category = app.get("category")
        if category:
            return category

        categories = search.get("categories")
        if isinstance(categories, list) and categories:
            first = categories[0]
            return first if isinstance(first, str) and first else None

        return None

    def _resolve_install_file_url(
        self,
        install: Dict[str, Any],
        repository_path: Any,
        app_id: Any,
        file_suffix: str,
    ) -> Optional[str]:
        files = install.get("files")
        if not isinstance(files, list):
            return None

        for file_path in files:
            if not isinstance(file_path, str) or not file_path:
                continue

            resolved_url = self._resolve_repository_file_url(
                value=file_path,
                repository_path=repository_path,
                app_id=app_id,
                file_name=file_suffix,
            )
            if resolved_url and resolved_url.endswith(file_suffix):
                return resolved_url

        return None

    def _resolve_repository_file_url(
        self,
        value: Any,
        repository_path: Any,
        app_id: Any,
        file_name: str,
    ) -> Optional[str]:
        canonical_repo_path = self._canonical_repository_path(repository_path, app_id)
        if not canonical_repo_path:
            return None

        relative_path = None
        if isinstance(value, str) and value.strip():
            relative_path = self._extract_relative_path(value)

        if not relative_path:
            return f"{CATALOG_RAW_BASE_URL}/{canonical_repo_path}/{file_name}"

        normalized_rel_path = relative_path
        if normalized_rel_path.startswith("apps/"):
            parts = normalized_rel_path.split("/")
            if len(parts) >= 3:
                normalized_rel_path = "/".join(parts[2:])
            else:
                normalized_rel_path = file_name
        elif (
            isinstance(app_id, str)
            and app_id
            and normalized_rel_path.startswith(f"{app_id}/")
        ):
            normalized_rel_path = normalized_rel_path[len(app_id) + 1 :]

        if not normalized_rel_path:
            normalized_rel_path = file_name
        if normalized_rel_path.endswith("/"):
            normalized_rel_path = f"{normalized_rel_path}{file_name}"
        if "/" not in normalized_rel_path:
            normalized_rel_path = file_name

        return f"{CATALOG_RAW_BASE_URL}/{canonical_repo_path}/{normalized_rel_path}"

    def _resolve_asset_url(
        self,
        value: Any,
        repository_path: Any,
        app_id: Any,
    ) -> Optional[str]:
        if not isinstance(value, str):
            return None

        raw_value = value.strip()
        if not raw_value:
            return None

        canonical_repo_path = self._canonical_repository_path(repository_path, app_id)
        if not canonical_repo_path:
            return raw_value

        if raw_value.startswith(CATALOG_RAW_BASE_URL):
            return raw_value

        relative_path = self._extract_relative_path(raw_value)
        if not relative_path:
            return raw_value

        rel_for_asset = relative_path
        if rel_for_asset.startswith("apps/"):
            parts = rel_for_asset.split("/")
            if len(parts) >= 4:
                rel_for_asset = "/".join(parts[2:])
            else:
                rel_for_asset = rel_for_asset.split("/")[-1]
        elif (
            isinstance(app_id, str)
            and app_id
            and rel_for_asset.startswith(f"{app_id}/")
        ):
            rel_for_asset = rel_for_asset[len(app_id) + 1 :]

        if not rel_for_asset.startswith("imgs/"):
            rel_for_asset = f"imgs/{rel_for_asset.split('/')[-1]}"

        normalized_path = f"{canonical_repo_path}/{rel_for_asset}"
        return f"{CATALOG_RAW_BASE_URL}/{normalized_path}"

    def _canonical_repository_path(
        self, repository_path: Any, app_id: Any
    ) -> Optional[str]:
        if isinstance(repository_path, str):
            cleaned = repository_path.strip().strip("/")
            if cleaned:
                if cleaned.startswith("apps/"):
                    return cleaned
                return f"apps/{cleaned}"

        if isinstance(app_id, str):
            cleaned_app_id = app_id.strip().strip("/")
            if cleaned_app_id:
                return f"apps/{cleaned_app_id}"

        return None

    def _extract_relative_path(self, value: str) -> Optional[str]:
        cleaned = value.strip().strip("/")
        if not cleaned:
            return None

        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            return cleaned

        without_scheme = cleaned.split("://", 1)[1]
        path = without_scheme.split("/", 1)[1] if "/" in without_scheme else ""
        if not path:
            return None

        if without_scheme.startswith("raw.githubusercontent.com/"):
            parts = path.split("/")
            if len(parts) >= 4:
                return "/".join(parts[3:])
            return parts[-1]

        return path

    def _build_source_raw_url(
        self, source: Dict[str, Any], file_path: str
    ) -> Optional[str]:
        repo_url = source.get("repo")
        commit = source.get("commit")
        if not isinstance(repo_url, str) or not isinstance(commit, str):
            return None
        if not repo_url or not commit:
            return None

        normalized_repo = repo_url.strip()
        if normalized_repo.startswith("git@github.com:"):
            normalized_repo = normalized_repo.replace(
                "git@github.com:", "https://github.com/"
            )
        if normalized_repo.endswith(".git"):
            normalized_repo = normalized_repo[:-4]
        if not normalized_repo.startswith("https://github.com/"):
            return None

        repo_path = normalized_repo.replace("https://github.com/", "", 1).strip("/")
        rel_path = file_path.lstrip("/")
        return f"https://raw.githubusercontent.com/{repo_path}/{commit}/{rel_path}"

    def _parse_source_updated_at(self, value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value:
            return None
        parsed_value = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(parsed_value)
        except ValueError:
            return None
