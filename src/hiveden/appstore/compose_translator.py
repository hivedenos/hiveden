import os
from typing import Any, Dict, List, Tuple

import yaml

from hiveden.docker.models import Device, EnvVar, Mount, Port


UNSUPPORTED_COMPOSE_KEYS = {"build", "secrets", "configs"}


class ComposeTranslationError(ValueError):
    pass


def parse_compose_yaml(content: str) -> Dict[str, Any]:
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise ComposeTranslationError("Compose file must be a YAML object")
    services = data.get("services")
    if not isinstance(services, dict) or not services:
        raise ComposeTranslationError("Compose file must define at least one service")
    return data


def translate_compose_services(
    app_id: str,
    compose_data: Dict[str, Any],
    env_overrides: Dict[str, str] | None = None,
) -> List[Dict[str, Any]]:
    services = compose_data.get("services", {})
    translated = []
    service_to_container: Dict[str, str] = {}

    for service_name, spec in services.items():
        if not isinstance(spec, dict):
            raise ComposeTranslationError(f"Service '{service_name}' must be a YAML object")
        unsupported = [key for key in spec if key in UNSUPPORTED_COMPOSE_KEYS]
        if unsupported:
            raise ComposeTranslationError(
                f"Service '{service_name}' uses unsupported keys: {', '.join(unsupported)}"
            )
        container_name = spec.get("container_name") or f"{app_id}-{service_name}"
        service_to_container[service_name] = container_name

    for service_name, spec in services.items():
        image = spec.get("image")
        if not image:
            raise ComposeTranslationError(f"Service '{service_name}' is missing required 'image'")

        container_name = service_to_container[service_name]
        command = _normalize_command(spec.get("command"))
        env = _normalize_environment(spec.get("environment"), env_overrides or {})
        ports = _normalize_ports(spec.get("ports"))
        mounts, app_dirs = _normalize_volumes(app_id, container_name, spec.get("volumes"))
        devices = _normalize_devices(spec.get("devices"))
        labels = _normalize_labels(spec.get("labels"), app_id, service_name)
        dependencies = _normalize_depends_on(spec.get("depends_on"), service_to_container)
        privileged = bool(spec.get("privileged", False))

        translated.append(
            {
                "name": container_name,
                "image": image,
                "command": command,
                "dependencies": dependencies,
                "env": env,
                "ports": ports,
                "mounts": mounts,
                "devices": devices,
                "labels": labels,
                "privileged": privileged,
                "app_directories": app_dirs,
            }
        )

    return translated


def _normalize_command(command: Any) -> List[str] | None:
    if command is None:
        return None
    if isinstance(command, list):
        return [str(item) for item in command]
    if isinstance(command, str):
        return command.split()
    raise ComposeTranslationError("Unsupported command format")


def _normalize_environment(environment: Any, overrides: Dict[str, str]) -> List[EnvVar] | None:
    values: Dict[str, str] = {}
    if isinstance(environment, dict):
        for key, value in environment.items():
            values[str(key)] = "" if value is None else str(value)
    elif isinstance(environment, list):
        for item in environment:
            if isinstance(item, str):
                if "=" in item:
                    k, v = item.split("=", 1)
                    values[k] = v
                else:
                    values[item] = ""
    elif environment is not None:
        raise ComposeTranslationError("Unsupported environment format")

    values.update({str(k): str(v) for k, v in overrides.items()})
    if not values:
        return None
    return [EnvVar(name=k, value=v) for k, v in values.items()]


def _normalize_ports(ports: Any) -> List[Port] | None:
    if ports is None:
        return None
    if not isinstance(ports, list):
        raise ComposeTranslationError("Ports must be a list")

    out: List[Port] = []
    for item in ports:
        if isinstance(item, str):
            proto = "tcp"
            raw = item
            if "/" in raw:
                raw, proto = raw.split("/", 1)
            parts = raw.split(":")
            if len(parts) == 2:
                host_port, container_port = parts
            elif len(parts) == 3:
                _, host_port, container_port = parts
            else:
                raise ComposeTranslationError(f"Unsupported port mapping '{item}'")
            out.append(
                Port(
                    host_port=int(host_port),
                    container_port=int(container_port),
                    protocol=proto,
                )
            )
        elif isinstance(item, dict):
            out.append(
                Port(
                    host_port=int(item["published"]),
                    container_port=int(item["target"]),
                    protocol=str(item.get("protocol", "tcp")),
                )
            )
        else:
            raise ComposeTranslationError("Unsupported port entry format")
    return out or None


def _normalize_volumes(
    app_id: str,
    container_name: str,
    volumes: Any,
) -> Tuple[List[Mount] | None, List[str]]:
    if volumes is None:
        return None, []
    if not isinstance(volumes, list):
        raise ComposeTranslationError("Volumes must be a list")

    mounts: List[Mount] = []
    app_dirs: List[str] = []
    for item in volumes:
        if isinstance(item, str):
            parts = item.split(":")
            if len(parts) < 2:
                raise ComposeTranslationError(f"Unsupported volume mapping '{item}'")
            source = parts[0]
            target = parts[1]
            mode = parts[2] if len(parts) > 2 else "rw"
            read_only = "ro" in mode.split(",")
            is_abs = source.startswith("/")
            is_rel = source.startswith("./") or source.startswith("../")
            is_named = not is_abs and not is_rel
            if is_named:
                app_source = os.path.join("volumes", source)
                mounts.append(
                    Mount(
                        source=app_source,
                        target=target,
                        is_app_directory=True,
                        read_only=read_only,
                    )
                )
                app_dirs.append(f"{container_name}/{app_source}")
            elif is_rel:
                rel = source.lstrip("./")
                mounts.append(
                    Mount(
                        source=rel,
                        target=target,
                        is_app_directory=True,
                        read_only=read_only,
                    )
                )
                app_dirs.append(f"{container_name}/{rel}")
            else:
                mounts.append(
                    Mount(
                        source=source,
                        target=target,
                        is_app_directory=False,
                        read_only=read_only,
                    )
                )
        elif isinstance(item, dict):
            source = str(item.get("source", ""))
            target = str(item.get("target", ""))
            if not source or not target:
                raise ComposeTranslationError("Volume objects must include source and target")
            vol_type = item.get("type", "volume")
            read_only = bool(item.get("read_only", False))
            if vol_type == "bind" and source.startswith("/"):
                mounts.append(Mount(source=source, target=target, is_app_directory=False, read_only=read_only))
            else:
                app_source = os.path.join("volumes", source)
                mounts.append(Mount(source=app_source, target=target, is_app_directory=True, read_only=read_only))
                app_dirs.append(f"{container_name}/{app_source}")
        else:
            raise ComposeTranslationError("Unsupported volume entry format")
    return mounts or None, app_dirs


def _normalize_devices(devices: Any) -> List[Device] | None:
    if devices is None:
        return None
    if not isinstance(devices, list):
        raise ComposeTranslationError("Devices must be a list")

    out: List[Device] = []
    for item in devices:
        if isinstance(item, str):
            parts = item.split(":")
            if len(parts) < 2:
                raise ComposeTranslationError(f"Unsupported device mapping '{item}'")
            host = parts[0]
            container = parts[1]
            perms = parts[2] if len(parts) > 2 else "rwm"
            out.append(
                Device(
                    path_on_host=host,
                    path_in_container=container,
                    cgroup_permissions=perms,
                )
            )
        elif isinstance(item, dict):
            out.append(
                Device(
                    path_on_host=str(item["path"]),
                    path_in_container=str(item.get("path_in_container", item["path"])),
                    cgroup_permissions=str(item.get("cgroup_permissions", "rwm")),
                )
            )
        else:
            raise ComposeTranslationError("Unsupported device entry format")
    return out or None


def _normalize_labels(labels: Any, app_id: str, service_name: str) -> Dict[str, str] | None:
    out: Dict[str, str] = {
        "managed-by": "hiveden",
        "hiveden.app.id": app_id,
        "hiveden.app.service": service_name,
    }
    if labels is None:
        return out
    if isinstance(labels, dict):
        out.update({str(k): str(v) for k, v in labels.items()})
    elif isinstance(labels, list):
        for item in labels:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                out[key] = value
    else:
        raise ComposeTranslationError("Unsupported labels format")
    return out


def _normalize_depends_on(depends_on: Any, mapping: Dict[str, str]) -> List[str] | None:
    if depends_on is None:
        return None
    if isinstance(depends_on, list):
        deps = [mapping.get(str(service), str(service)) for service in depends_on]
        return deps or None
    if isinstance(depends_on, dict):
        deps = [mapping.get(str(service), str(service)) for service in depends_on.keys()]
        return deps or None
    raise ComposeTranslationError("Unsupported depends_on format")

