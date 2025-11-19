import psutil

from hiveden.hwosinfo.os import get_os_info

try:
    import libzfs
except ImportError:
    os_info = get_os_info()
    distro = os_info.get("id").lower()
    if distro in ["arch"]:
        raise ImportError("py-libzfs is not installed. Please install it with: pacman -S python-pylibzfs")
    elif distro in ["debian", "ubuntu"]:
        raise ImportError("py-libzfs is not installed. Please install it with: apt-get install py-libzfs")
    else:
        raise ImportError("py-libzfs is not installed. Please install it using your system package manager.")

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
    used_devices = []
    try:
        zfs = libzfs.ZFS()
        for pool in zfs.pools:
            for vdev in pool.vdev_tree.children:
                if vdev.is_leaf:
                    used_devices.append(vdev.path)
    except Exception:
        # libzfs not installed or no pools exist
        pass

    return [d for d in all_devices if d not in used_devices]
