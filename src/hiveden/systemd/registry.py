# Dictionary of managed services.
# Key: Internal ID/Name used in API
# Value: List of possible systemd unit names (first match wins)

MANAGED_SERVICES = {
    "smb": ["smb.service"],
    "ssh": ["ssh.service", "sshd.service"],
    "docker": ["docker.service"],
    "cron": ["cron.service", "crond.service"]
}
