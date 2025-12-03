import pytest
from hiveden.storage.strategies import generate_strategies
from hiveden.storage.models import Disk

def create_mock_disk(name, size_gb):
    return Disk(
        name=name,
        path=f"/dev/{name}",
        size=size_gb * 1024 * 1024 * 1024,
        rotational=True,
        available=True
    )

def test_strategies_one_disk():
    disks = [create_mock_disk("sdb", 1000)]
    strategies = generate_strategies(disks)
    
    # Should only suggest JBOD/Single
    assert len(strategies) == 1
    assert strategies[0].raid_level == "raid0" # Treated as stripe of 1
    assert strategies[0].name == "Maximum Capacity (JBOD)"

def test_strategies_two_disks():
    disks = [create_mock_disk("sdb", 1000), create_mock_disk("sdc", 1000)]
    strategies = generate_strategies(disks)
    
    # Should suggest JBOD and RAID1
    raid_levels = [s.raid_level for s in strategies]
    assert "raid0" in raid_levels
    assert "raid1" in raid_levels
    assert "raid5" not in raid_levels

def test_strategies_three_disks():
    disks = [
        create_mock_disk("sdb", 1000),
        create_mock_disk("sdc", 1000),
        create_mock_disk("sdd", 1000)
    ]
    strategies = generate_strategies(disks)
    
    raid_levels = [s.raid_level for s in strategies]
    assert "raid0" in raid_levels
    assert "raid1" in raid_levels
    assert "raid5" in raid_levels
    assert "raid6" not in raid_levels

def test_strategies_four_disks():
    disks = [create_mock_disk("sd" + str(i), 1000) for i in range(4)]
    strategies = generate_strategies(disks)
    
    raid_levels = [s.raid_level for s in strategies]
    assert "raid0" in raid_levels
    assert "raid1" in raid_levels
    assert "raid5" in raid_levels
    assert "raid6" in raid_levels
    assert "raid10" in raid_levels
