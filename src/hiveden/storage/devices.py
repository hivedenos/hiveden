from typing import List
from hiveden.hwosinfo.hw import get_disks as get_raw_disks
from hiveden.storage.models import Disk, Partition

def get_system_disks() -> List[Disk]:
    """
    Retrieves system disks and parses them into Disk models.
    Determines availability based on partitions and mount points.
    """
    raw_data = get_raw_disks()
    disks = []

    for device in raw_data:
        # Skip loop devices and ram disks
        if device.get("name", "").startswith("loop") or device.get("name", "").startswith("ram"):
            continue

        # Parse partitions
        partitions = []
        is_system = False
        
        # lsblk nests partitions under 'children'
        raw_partitions = device.get("children", [])
        
        for p in raw_partitions:
            mountpoint = p.get("mountpoint")
            
            # Check for system mount points
            if mountpoint in ["/", "/boot", "/boot/efi", "/etc", "/var", "/usr"]:
                is_system = True
            
            # Also check for swap
            if p.get("fstype") == "swap":
                is_system = True

            partitions.append(Partition(
                name=p.get("name"),
                path=p.get("path"),
                size=int(p.get("size") or 0),
                fstype=p.get("fstype"),
                uuid=p.get("uuid"),
                mountpoint=mountpoint
            ))
        
        # If disk itself has a mountpoint (filesystem directly on disk)
        if device.get("mountpoint"):
            if device.get("mountpoint") in ["/", "/boot", "/boot/efi"]:
                is_system = True

        # Determine availability:
        # Considered available if not system disk and has no partitions 
        # OR has partitions but they are not mounted (though this is risky, so let's stick to empty for now)
        # Ideally, we'd check for partition table signatures, but lsblk children check is a good proxy.
        # For safety: Available only if NO children and NO fstype on the disk itself.
        available = not is_system and not raw_partitions and not device.get("fstype")

        disk = Disk(
            name=device.get("name"),
            path=device.get("path"),
            size=int(device.get("size") or 0),
            model=device.get("model"),
            serial=device.get("serial"),
            rotational=bool(device.get("rota")),
            partitions=partitions,
            is_system=is_system,
            available=available
        )
        disks.append(disk)

    return disks

def get_unused_disks() -> List[Disk]:
    """Returns only disks marked as available."""
    return [d for d in get_system_disks() if d.available]
