from typing import List
from hiveden.storage.devices import get_system_disks, get_unused_disks
from hiveden.storage.strategies import generate_strategies
from hiveden.storage.models import Disk, StorageStrategy
from hiveden.jobs.manager import JobManager

class StorageManager:
    def list_disks(self) -> List[Disk]:
        return get_system_disks()

    def get_strategies(self) -> List[StorageStrategy]:
        unused = get_unused_disks()
        return generate_strategies(unused)

    def apply_strategy(self, strategy: StorageStrategy) -> str:
        """
        Applies the given storage strategy.
        Returns the Job ID of the background task.
        """
        commands = []
        mount_point = "/mnt/hiveden-storage"
        
        commands.append(f"echo 'Starting configuration for {strategy.name}...'")
        
        # 1. Cleanup and Prepare Disks
        disks_str = " ".join(strategy.disks)
        
        # Unmount any existing mounts on these disks (best effort) and wipe
        for disk in strategy.disks:
            commands.append(f"echo 'Preparing {disk}...'")
            # lazy unmount to avoid busy errors, || true to ignore if not mounted
            commands.append(f"umount -l {disk}* 2>/dev/null || true")
            commands.append(f"wipefs -a {disk}")
        
        mount_dev = ""

        if strategy.raid_level == "single":
            # Btrfs single mode (JBOD)
            commands.append(f"echo 'Formatting disks in Single mode...'")
            # -f: force, -d single: data single, -m single: metadata single
            commands.append(f"mkfs.btrfs -f -d single -m single {disks_str}")
            mount_dev = strategy.disks[0] # Mount any device in the pool
            
        elif strategy.raid_level.startswith("raid"):
            level = strategy.raid_level.replace("raid", "")
            md_dev = "/dev/md0"
            mount_dev = md_dev
            
            commands.append(f"echo 'Configuring RAID {level}...'")
            
            # Stop existing array if it exists
            commands.append(f"mdadm --stop {md_dev} 2>/dev/null || true")
            
            # Zero superblocks on all disks to remove old raid info
            commands.append(f"mdadm --zero-superblock {disks_str} 2>/dev/null || true")
            
            # Create Array
            commands.append(f"mdadm --create {md_dev} --level={level} --raid-devices={len(strategy.disks)} {disks_str} --run --force")
            
            # Format
            commands.append(f"echo 'Formatting RAID array...'")
            commands.append(f"mkfs.btrfs -f {md_dev}")

        # Mounting
        commands.append(f"echo 'Mounting storage to {mount_point}...'")
        commands.append(f"mkdir -p {mount_point}")
        commands.append(f"mount {mount_dev} {mount_point}")
        
        commands.append("echo 'Storage configuration completed successfully.'")
        
        # Join commands into a single shell command
        full_command = " && ".join(commands)
        
        # Submit to JobManager
        job_manager = JobManager()
        return job_manager.create_job(full_command)
