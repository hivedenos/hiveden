import json
from typing import Any, Dict
from urllib.request import Request, urlopen


class CatalogClient:
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def fetch_catalog(self, index_url: str) -> Dict[str, Any]:
        request = Request(index_url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("Catalog payload must be a JSON object")
            self._validate_catalog_payload(data)
            return data

    def _validate_catalog_payload(self, data: Dict[str, Any]):
        required_top_level = ["version", "generated_at", "total_apps", "apps"]
        missing = [key for key in required_top_level if key not in data]
        if missing:
            raise ValueError(
                "Catalog payload missing required keys: " + ", ".join(missing)
            )

        apps = data.get("apps")
        if not isinstance(apps, list):
            raise ValueError("Catalog payload 'apps' must be an array")

        apps_by_channel = data.get("apps_by_channel")
        if apps_by_channel is not None and not isinstance(apps_by_channel, dict):
            raise ValueError("Catalog payload 'apps_by_channel' must be an object")

        required_app_keys = [
            "id",
            "name",
            "version",
            "tagline",
            "description",
            "repository_path",
            "icon_url",
            "image_urls",
            "source",
            "install",
            "search",
            "dependencies",
            "updated_at",
        ]

        self._validate_app_list(apps, required_app_keys)

        if isinstance(apps_by_channel, dict):
            for channel, channel_apps in apps_by_channel.items():
                if not isinstance(channel_apps, list):
                    raise ValueError(
                        "Catalog channel "
                        f"'{channel}' payload 'apps_by_channel' must be an array"
                    )
                self._validate_app_list(channel_apps, required_app_keys)

    def _validate_app_list(self, apps: list, required_app_keys: list[str]):
        for index, app in enumerate(apps):
            if not isinstance(app, dict):
                raise ValueError(f"Catalog app at index {index} must be an object")
            missing_app_keys = [key for key in required_app_keys if key not in app]
            if missing_app_keys:
                raise ValueError(
                    "Catalog app at index "
                    f"{index} missing required keys: {', '.join(missing_app_keys)}"
                )
