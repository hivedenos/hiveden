import json
import subprocess

import psutil

from hiveden.shares.zfs import ZFSManager


def get_disks():
    """Return a list of disks and their partitions."""
    output = subprocess.check_output(["lsblk", "-J", "-b"]).decode()
    data = json.loads(output)
    return data["blockdevices"]


def get_hw_info():
    """Return a dictionary with hardware information."""
    info = {
        'cpu': {
            'physical_cores': psutil.cpu_count(logical=False),
            'total_cores': psutil.cpu_count(logical=True),
            'max_frequency': psutil.cpu_freq().max,
            'min_frequency': psutil.cpu_freq().min,
            'current_frequency': psutil.cpu_freq().current,
            'cpu_usage_per_core': psutil.cpu_percent(percpu=True),
            'total_cpu_usage': psutil.cpu_percent(),
        },
        'memory': {
            'total': psutil.virtual_memory().total,
            'available': psutil.virtual_memory().available,
            'used': psutil.virtual_memory().used,
            'percentage': psutil.virtual_memory().percent,
        },
        'disk': {
            'partitions': [p.device for p in psutil.disk_partitions()],
            'total': psutil.disk_usage('/').total,
            'used': psutil.disk_usage('/').used,
            'free': psutil.disk_usage('/').free,
            'percentage': psutil.disk_usage('/').percent,
        },
        'network': {
            'interfaces': list(psutil.net_if_addrs().keys()),
            'io_counters': psutil.net_io_counters()._asdict(),
        }
    }
    return info


def get_available_devices():
    """Return a list of devices available for ZFS pools."""
    all_devices = [p.device for p in psutil.disk_partitions()]
    manager = ZFSManager()
    used_devices = manager.get_all_devices()

    return [d for d in all_devices if d not in used_devices]
