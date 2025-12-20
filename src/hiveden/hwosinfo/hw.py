import json
import subprocess
import socket

import psutil
from hiveden.hwosinfo.models import NetworkAddress, NetworkInterface, NetworkIOCounters, NetworkInfo, HWInfo

def get_disks():
    """Return a list of disks and their partitions with detailed info."""
    # -J: JSON output
    # -b: Bytes
    # -o: Specific columns
    cmd = ["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,MODEL,SERIAL,ROTA,TYPE,FSTYPE,UUID,MOUNTPOINT,PKNAME"]
    output = subprocess.check_output(cmd).decode()
    data = json.loads(output)
    return data["blockdevices"]


def get_host_ip():
    """Retrieves the primary IP address of the host."""
    try:
        # Create a dummy socket to connect to an external IP (Cloudflare DNS)
        # We don't actually send data, just need the OS to tell us which interface it would use
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(('1.1.1.1', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        
        if ip != '127.0.0.1':
            return ip
            
        # Fallback: iterate over interfaces
        interfaces = psutil.net_if_addrs()
        for interface, addrs in interfaces.items():
            if interface == 'lo': 
                continue
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    return addr.address
        return '127.0.0.1'

    except Exception:
        return '127.0.0.1'


def get_hw_info() -> HWInfo:
    """Return a dictionary with hardware information."""
    
    # Process network interfaces to be JSON serializable and more informative
    net_if_addrs = psutil.net_if_addrs()
    network_interfaces = {}
    
    for iface_name, iface_addresses in net_if_addrs.items():
        addresses = []
        for addr in iface_addresses:
            family_str = str(addr.family)
            if addr.family == socket.AF_INET:
                family_str = 'IPv4'
            elif addr.family == socket.AF_INET6:
                family_str = 'IPv6'
            elif hasattr(socket, 'AF_PACKET') and addr.family == socket.AF_PACKET:
                family_str = 'MAC'
            
            addresses.append(NetworkAddress(
                address=addr.address,
                netmask=addr.netmask,
                broadcast=addr.broadcast,
                ptp=addr.ptp,
                family=family_str
            ))
        network_interfaces[iface_name] = NetworkInterface(addresses=addresses)

    io_counters = psutil.net_io_counters()
    network_io_counters = NetworkIOCounters(
        bytes_sent=io_counters.bytes_sent,
        bytes_recv=io_counters.bytes_recv,
        packets_sent=io_counters.packets_sent,
        packets_recv=io_counters.packets_recv,
        errin=io_counters.errin,
        errout=io_counters.errout,
        dropin=io_counters.dropin,
        dropout=io_counters.dropout,
    )

    network_info = NetworkInfo(
        interfaces=network_interfaces,
        io_counters=network_io_counters,
        primary_ip=get_host_ip()
    )

    hw_info = HWInfo(
        cpu={
            'physical_cores': psutil.cpu_count(logical=False),
            'total_cores': psutil.cpu_count(logical=True),
            'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else 0,
            'min_frequency': psutil.cpu_freq().min if psutil.cpu_freq() else 0,
            'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            'cpu_usage_per_core': psutil.cpu_percent(percpu=True),
            'total_cpu_usage': psutil.cpu_percent(),
        },
        memory={
            'total': psutil.virtual_memory().total,
            'available': psutil.virtual_memory().available,
            'used': psutil.virtual_memory().used,
            'percentage': psutil.virtual_memory().percent,
        },
        disk={
            'partitions': [p.device for p in psutil.disk_partitions()],
            'total': psutil.disk_usage('/').total,
            'used': psutil.disk_usage('/').used,
            'free': psutil.disk_usage('/').free,
            'percentage': psutil.disk_usage('/').percent,
        },
        network=network_info
    )
    return hw_info


def get_smart_info(device_path: str) -> dict:
    """
    Retrieves S.M.A.R.T. data for a device using smartctl.
    Returns a raw dictionary from the JSON output.
    """
    try:
        # -a: All info, -j: JSON
        cmd = ["smartctl", "-a", "-j", device_path]
        # smartctl returns exit code with bitmask. 
        # Even if it succeeds reading, it might have non-zero exit code if disk is failing.
        # So we capture output and ignore return code mostly, unless it failed to run.
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if not result.stdout:
            return {}

        data = json.loads(result.stdout)
        return data
    except Exception:
        return {}
