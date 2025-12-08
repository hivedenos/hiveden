import shutil
import configparser
import subprocess
import os
from hiveden.pkgs.manager import get_package_manager
from hiveden.hwosinfo.os import get_os_info
from hiveden.shares.models import SMBShare

SMB_CONF_PATH = "/etc/samba/smb.conf"

class SMBManager:
    def check_installed(self):
        """Check if samba is installed."""
        # Check for smbd executable
        return shutil.which("smbd") is not None or shutil.which("samba") is not None

    def install(self):
        """Install samba."""
        if self.check_installed():
            return

        pm = get_package_manager()
        # Most distros use 'samba'
        pm.install("samba")

    def _str_to_bool(self, val: str) -> bool:
        return val.lower() in ('yes', 'true', '1', 'on')

    def list_shares(self):
        """List all samba shares."""
        if not os.path.exists(SMB_CONF_PATH):
            return []

        config = configparser.ConfigParser()
        try:
            config.read(SMB_CONF_PATH)
        except configparser.Error:
            # Fallback or return empty if file is malformed
            return []

        shares = []
        for section in config.sections():
            # global, printers, print$ are standard sections/shares we might want to skip or mark
            if section.lower() == 'global':
                continue
            
            shares.append(SMBShare(
                name=section,
                path=config[section].get('path', 'N/A'),
                comment=config[section].get('comment', ''),
                read_only=self._str_to_bool(config[section].get('read only', 'yes')),
                browsable=self._str_to_bool(config[section].get('browsable', 'yes')),
                guest_ok=self._str_to_bool(config[section].get('guest ok', 'no'))
            ))
        return shares

    def create_share(self, name, path, comment="", readonly=False, browsable=True, guest_ok=False):
        """Create a new samba share."""
        if not os.path.exists(SMB_CONF_PATH):
            # If config doesn't exist, create a basic one
            self._create_base_config()

        config = configparser.ConfigParser()
        config.read(SMB_CONF_PATH)

        if name in config:
            raise ValueError(f"Share '{name}' already exists.")

        config[name] = {
            'path': path,
            'comment': comment,
            'read only': 'yes' if readonly else 'no',
            'browsable': 'yes' if browsable else 'no',
            'guest ok': 'yes' if guest_ok else 'no'
        }

        with open(SMB_CONF_PATH, 'w') as configfile:
            config.write(configfile)

        self._reload_service()

    def delete_share(self, name):
        """Delete a samba share."""
        if not os.path.exists(SMB_CONF_PATH):
            raise ValueError("Samba configuration file not found.")

        config = configparser.ConfigParser()
        config.read(SMB_CONF_PATH)

        if name not in config:
            raise ValueError(f"Share '{name}' does not exist.")

        config.remove_section(name)

        with open(SMB_CONF_PATH, 'w') as configfile:
            config.write(configfile)

        self._reload_service()

    def start_service(self):
        """Start the samba service."""
        self._manage_service("start")

    def stop_service(self):
        """Stop the samba service."""
        self._manage_service("stop")

    def restart_service(self):
        """Restart the samba service."""
        self._manage_service("restart")

    def get_status(self):
        """Get the status of the samba service."""
        service_names = ['smbd', 'samba', 'smb']
        for service in service_names:
            try:
                result = subprocess.run(["systemctl", "is-active", service], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                status = result.stdout.strip()
                if status != "unknown":
                    return status
            except FileNotFoundError:
                continue
        return "not found"

    def _create_base_config(self):
        config = configparser.ConfigParser()
        config['global'] = {
            'workgroup': 'WORKGROUP',
            'server string': 'Hiveden Server',
            'security': 'user',
            'map to guest': 'Bad User'
        }
        os.makedirs(os.path.dirname(SMB_CONF_PATH), exist_ok=True)
        with open(SMB_CONF_PATH, 'w') as configfile:
            config.write(configfile)

    def _reload_service(self):
        """Reload the samba service."""
        self._manage_service("reload")

    def _manage_service(self, action):
        """Manage the samba service state."""
        service_names = ['smbd', 'samba', 'smb']
        for service in service_names:
            try:
                subprocess.run(["systemctl", action, service], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        # If all fail, it might be worth logging or raising a warning, but for now we stay silent or maybe raise if strict.
        # For CLI usage, silent failure if service isn't found might be confusing, but consistent with previous implementation.
