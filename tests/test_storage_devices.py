import pytest
from unittest.mock import Mock, patch
from hiveden.storage.devices import get_system_disks, get_unused_disks
from hiveden.storage.models import Disk, Partition

# Mock raw data from lsblk
MOCK_LSBLK_DATA = [
    {
        "name": "sda",
        "path": "/dev/sda",
        "size": "500107862016",
        "model": "Samsung SSD 850",
        "serial": "S21JNSAG123456",
        "rota": False,
        "type": "disk",
        "children": [
            {"name": "sda1", "path": "/dev/sda1", "size": "536870912", "fstype": "vfat", "mountpoint": "/boot/efi"},
            {"name": "sda2", "path": "/dev/sda2", "size": "499570991104", "fstype": "ext4", "mountpoint": "/"}
        ]
    },
    {
        "name": "sdb",
        "path": "/dev/sdb",
        "size": "4000787030016",
        "model": "WD Red",
        "serial": "WD-WCC4E1234567",
        "rota": True,
        "type": "disk",
        "children": [] # Empty disk
    },
    {
        "name": "sdc",
        "path": "/dev/sdc",
        "size": "4000787030016",
        "model": "WD Red",
        "serial": "WD-WCC4E7654321",
        "rota": True,
        "type": "disk",
        "fstype": None,
        "children": [] # Empty disk
    }
]

@patch('hiveden.storage.devices.get_raw_disks')
def test_get_system_disks_parsing(mock_get_raw):
    mock_get_raw.return_value = MOCK_LSBLK_DATA
    
    disks = get_system_disks()
    
    assert len(disks) == 3
    
    # Check System Disk (sda)
    sda = next(d for d in disks if d.name == "sda")
    assert sda.is_system is True
    assert sda.available is False
    assert len(sda.partitions) == 2
    assert sda.model == "Samsung SSD 850"
    
    # Check Empty Disk (sdb)
    sdb = next(d for d in disks if d.name == "sdb")
    assert sdb.is_system is False
    assert sdb.available is True
    assert len(sdb.partitions) == 0

@patch('hiveden.storage.devices.get_raw_disks')
def test_get_unused_disks(mock_get_raw):
    mock_get_raw.return_value = MOCK_LSBLK_DATA
    
    unused = get_unused_disks()
    
    assert len(unused) == 2
    assert all(d.name in ["sdb", "sdc"] for d in unused)
