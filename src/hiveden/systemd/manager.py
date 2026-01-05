import logging
# from fastapi.logger import logger # Deprecated
logger = logging.getLogger(__name__)
import subprocess
import shutil
from typing import List, Optional
from hiveden.systemd.models import SystemdServiceStatus
from hiveden.systemd.registry import MANAGED_SERVICES

class SystemdManager:
    def _resolve_service_name(self, service_key: str) -> Optional[str]:
        """Resolves the actual systemd unit name from the registry list."""
        # check if service_key is in MANAGED_SERVICES
        if service_key not in MANAGED_SERVICES.keys():
            logger.info(f"Service {service_key} not found in registry, candidates: {MANAGED_SERVICES.keys()}")
            return None
        
        candidates = MANAGED_SERVICES[service_key]
        
        # If it's a direct unit name (ending in .service), check if it exists directly
        if service_key.endswith(".service"):
             candidates = [service_key]

        for unit in candidates:
            # Check if unit exists/is loaded
            # systemctl list-units --all --plain --no-legend <unit>
            try:
                # We use 'systemctl show' to check existence more reliably even if inactive
                res = subprocess.run(
                    ["systemctl", "show", "-p", "LoadState", unit], 
                    capture_output=True, text=True
                )

                logger.info(f"Resolved service name: {unit}, candidates: {candidates}, service name: {service_key}, output: {res.stdout}")
                if "LoadState=loaded" in res.stdout:
                    return unit
                elif "LoadState=not-found" in res.stdout:
                    continue
            except FileNotFoundError:
                return None
        return None

    def get_service_status(self, service_name: str) -> Optional[SystemdServiceStatus]:
        """Get comprehensive status of a service."""
        unit = self._resolve_service_name(service_name)
        logger.info(f"Resolved service name: {unit}, service name: {service_name}")
        if not unit:
            # Try to return a stub if it's a known managed service but not installed
            if service_name in MANAGED_SERVICES:
                return SystemdServiceStatus(
                    name=service_name,
                    load_state="not-found",
                    active_state="inactive",
                    sub_state="dead",
                    unit_file_state="disabled"
                )
            return None

        # Gather properties
        # LoadState, ActiveState, SubState, UnitFileState, Description, MainPID, ActiveEnterTimestamp
        props = ["LoadState", "ActiveState", "SubState", "UnitFileState", "Description", "MainPID", "ActiveEnterTimestamp"]
        cmd = ["systemctl", "show", "--no-pager"] + [f"-p{p}" for p in props] + [unit]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = {}
            for line in result.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k] = v.strip()
            
            # UnitFileState sometimes needs 'systemctl is-enabled' check if missing from show
            if not data.get("UnitFileState"):
                try:
                    res_enabled = subprocess.run(["systemctl", "is-enabled", unit], capture_output=True, text=True)
                    data["UnitFileState"] = res_enabled.stdout.strip()
                except:
                    data["UnitFileState"] = "unknown"

            logger.info(f"Service status: {data}, service name: {service_name}, unit: {unit}")

            return SystemdServiceStatus(
                name=service_name, # Return the API key name, or unit? Better to return unit name if resolved? 
                                   # No, keep API consistent with request. But maybe add real_name field?
                                   # For now, using requested name as ID.
                description=data.get("Description"),
                load_state=data.get("LoadState", "unknown"),
                active_state=data.get("ActiveState", "unknown"),
                sub_state=data.get("SubState", "unknown"),
                unit_file_state=data.get("UnitFileState", "unknown"),
                main_pid=int(data.get("MainPID", 0)),
                since=data.get("ActiveEnterTimestamp")
            )
        except Exception as e:
            logger.error(f"Error getting status for {unit}: {e}")
            return None

    def list_services(self) -> List[SystemdServiceStatus]:
        """List status for all managed services."""
        results = []
        for key in MANAGED_SERVICES.keys():
            status = self.get_service_status(key)
            if status:
                results.append(status)
        return results

    def manage_service(self, service_name: str, action: str):
        """Perform an action on a service."""
        if action not in ["start", "stop", "restart", "enable", "disable", "reload"]:
            raise ValueError(f"Invalid action: {action}")

        unit = self._resolve_service_name(service_name)
        if not unit:
            raise ValueError(f"Service {service_name} not found or not installed.")

        # sudo required usually, relying on hiveden running as root
        cmd = ["systemctl", action, unit]
        subprocess.run(cmd, check=True)
        
        return self.get_service_status(service_name)
