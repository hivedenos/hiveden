from typing import List
from hiveden.storage.models import StorageStrategy, Disk

def generate_strategies(disks: List[Disk]) -> List[StorageStrategy]:
    """
    Generates RAID/Storage strategies based on provided disks.
    """
    strategies = []
    count = len(disks)
    
    if count == 0:
        return strategies

    total_size = sum(d.size for d in disks)
    min_size = min(d.size for d in disks) if disks else 0

    # 1. Single Disk / JBOD (Always available)
    strategies.append(StorageStrategy(
        name="Maximum Capacity (JBOD)",
        description="Combines all drives. No redundancy. Total data loss if one drive fails.",
        raid_level="raid0", # Using RAID0 as proxy for spanning/striping
        disks=[d.path for d in disks],
        usable_capacity=total_size,
        redundancy="None"
    ))

    # 2. RAID 1 (Mirrored) - Requires at least 2 disks
    if count >= 2:
        # For RAID1 with N disks, capacity is usually size of smallest disk (N-way mirror)
        # Or pairs. Let's assume simple N-way mirror for safety or simple pair if count is even.
        # For simplicity in this proposal: RAID1 across all selected disks (N copies)
        strategies.append(StorageStrategy(
            name=f"Full Mirror (RAID 1)",
            description=f"Mirrors data across all {count} drives. Very high reliability, low capacity.",
            raid_level="raid1",
            disks=[d.path for d in disks],
            usable_capacity=min_size,
            redundancy=f"Can withstand {count - 1} drive failures"
        ))

    # 3. RAID 5 (Striping with Parity) - Requires at least 3 disks
    if count >= 3:
        raid5_cap = min_size * (count - 1)
        strategies.append(StorageStrategy(
            name="Balanced (RAID 5)",
            description="Striping with distributed parity. Good balance of speed and storage.",
            raid_level="raid5",
            disks=[d.path for d in disks],
            usable_capacity=raid5_cap,
            redundancy="Can withstand 1 drive failure"
        ))

    # 4. RAID 6 (Double Parity) - Requires at least 4 disks
    if count >= 4:
        raid6_cap = min_size * (count - 2)
        strategies.append(StorageStrategy(
            name="High Availability (RAID 6)",
            description="Striping with double parity. High reliability.",
            raid_level="raid6",
            disks=[d.path for d in disks],
            usable_capacity=raid6_cap,
            redundancy="Can withstand 2 drive failures"
        ))

    # 5. RAID 10 (Mirrored Stripes) - Requires at least 4 disks, even number
    if count >= 4 and count % 2 == 0:
        raid10_cap = min_size * (count / 2)
        strategies.append(StorageStrategy(
            name="Speed & Redundancy (RAID 10)",
            description="Striped mirrors. Excellent performance and redundancy.",
            raid_level="raid10",
            disks=[d.path for d in disks],
            usable_capacity=int(raid10_cap),
            redundancy="Can withstand 1 drive failure per mirror pair"
        ))

    return strategies
