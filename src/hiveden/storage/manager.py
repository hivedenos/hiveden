from typing import List, Optional
import os
import subprocess
from hiveden.storage.devices import get_system_disks, get_unused_disks
from hiveden.storage.strategies import generate_strategies
from hiveden.storage.models import Disk, StorageStrategy, DiskDetail, SmartData
from hiveden.jobs.manager import JobManager
from hiveden.hwosinfo.hw import get_smart_info

class StorageManager:
    def list_disks(self) -> List[Disk]:
        return get_system_disks()

    def get_disk_details(self, device_name: str) -> Optional[DiskDetail]:
        """
        Retrieves detailed information for a specific disk, including SMART data.
        """
        all_disks = get_system_disks()
        target_disk = next((d for d in all_disks if d.name == device_name), None)
        
        if not target_disk:
            return None

        # Get SMART info
        # Usually smartctl needs full path, e.g. /dev/sda
        # Our disk.path should have it.
        smart_raw = get_smart_info(target_disk.path)
        
        smart_data = None
        vendor = None
        firmware = None
        bus = None # smartctl often tells protocol

        if smart_raw:
            # Parse SmartData from raw JSON
            # Structure depends on smartctl version and device type
            # Basic parsing attempt:
            smart_status = smart_raw.get("smart_status", {})
            passed = smart_status.get("passed", False)
            
            # Temperature
            temp = smart_raw.get("temperature", {}).get("current")
            
            # Power on hours
            poh = smart_raw.get("power_on_time", {}).get("hours")
            
            # Power cycles
            cycles = smart_raw.get("power_cycle_count")

            # Model/Serial/Firmware often in 'model_name', 'serial_number', 'firmware_version' keys
            # or inside 'device' key
            device_info = smart_raw.get("device", {})
            model = smart_raw.get("model_name") or device_info.get("model_name")
            serial = smart_raw.get("serial_number") or device_info.get("serial_number")
            firmware = smart_raw.get("firmware_version") or device_info.get("firmware_version")
            
            # Rotation rate
            rotation = smart_raw.get("rotation_rate")
            
            # Attributes table
            ata_smart = smart_raw.get("ata_smart_attributes", {})
            attributes = ata_smart.get("table", [])

            smart_data = SmartData(
                healthy=passed,
                health_status="Passed" if passed else "Failed",
                temperature=temp,
                power_on_hours=poh,
                power_cycles=cycles,
                model_name=model,
                serial_number=serial,
                firmware_version=firmware,
                rotation_rate=rotation,
                attributes=attributes
            )
            
            # Vendor/Bus often in device info
            # protocol: "ATA", "SCSI", "NVMe"
            bus = device_info.get("protocol")

        return DiskDetail(
            **target_disk.dict(),
            vendor=vendor, # Might be extracted from model or lsblk
            bus=bus,
            smart=smart_data
        )

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

    def add_disk_to_raid(self, md_device: str, new_disk_path: str, target_raid_level: Optional[str] = None) -> str:
        """
        Adds a disk to an existing RAID array, optionally changing the RAID level.
        Returns the Job ID.
        """
        commands = []
        
        # 1. Prepare the new disk
        commands.append(f"echo 'Preparing {new_disk_path}...'")
        commands.append(f"umount -l {new_disk_path}* 2>/dev/null || true")
        commands.append(f"wipefs -a {new_disk_path}")
        
        # 2. Add as spare
        commands.append(f"echo 'Adding {new_disk_path} to {md_device}...'")
        commands.append(f"mdadm --manage {md_device} --add {new_disk_path}")
        
        # 3. Determine Grow Parameters
        # We need to know current active devices count to increment it
        # Since this runs in a job, we use shell calculation or assume the manager passed checked info.
        # Ideally, we query mdadm detail.
        # "mdadm --detail /dev/md0 | grep 'Active Devices' | awk '{print $4}'"
        
        commands.append(f"ACTIVE_DEVS=$(mdadm --detail {md_device} | grep 'Active Devices' | awk '{{print $NF}}')")
        commands.append("NEW_COUNT=$((ACTIVE_DEVS + 1))")
        
        grow_cmd = f"mdadm --grow {md_device} --raid-devices=$NEW_COUNT"
        
        if target_raid_level:
            # Strip 'raid' prefix if present (e.g. raid5 -> 5)
            level = target_raid_level.replace("raid", "")
            grow_cmd += f" --level={level}"
            commands.append(f"echo 'Growing array to {new_disk_path} devices and converting to RAID {level}...'")
            
            # Special case: RAID1 -> RAID5 usually requires a backup file unless "--backup-file" is specified 
            # or if using a modern kernel/mdadm capable of internal backup.
            # For safety, we should probably specify a backup file if transitioning levels, 
            # but that requires a separate filesystem. 
            # Modern mdadm often handles this in memory or requires a file.
            # Let's try adding --backup-file only if needed is risky without knowing FS layout.
            # We will assume standard growth. If it fails, the job fails.
        else:
            commands.append(f"echo 'Growing array to $NEW_COUNT devices...'")

        commands.append(grow_cmd)
        
        # 4. Wait for reshape/sync? 
        # btrfs resize can usually happen while it's syncing, but safest to wait or just trigger it.
        # If we just expanded the device, we should tell btrfs to maximize usage.
        
        # We need the mountpoint of the md device to run btrfs filesystem resize
        # simple hack: find where it matches in mount
        # "findmnt -n -o TARGET --source /dev/md0"
        
        commands.append(f"MOUNTPOINT=$(findmnt -n -o TARGET --source {md_device})")
        commands.append(f"if [ -z \"$MOUNTPOINT\" ]; then echo 'Device not mounted, skipping FS resize'; else echo 'Resizing filesystem at $MOUNTPOINT...'; btrfs filesystem resize max $MOUNTPOINT; fi")
        
        commands.append("echo 'RAID expansion initiated successfully.'")
        
        full_command = " && ".join(commands)
        job_manager = JobManager()
        return job_manager.create_job(full_command)

    def mount_partition(self, device: str, automatic: bool, mount_name: Optional[str]) -> str:
        """
        Mounts a partition to a directory in /mnt.
        
        Args:
            device: The device path (e.g., /dev/sdb1)
            automatic: Whether to automatically generate the mount name
            mount_name: The desired mount name (if automatic is False)
            
        Returns:
            The path where the device was mounted.
        """
        base_mount_path = "/mnt"
        
        target_name = ""
        if automatic:
            # Derive name from device, e.g. /dev/sdb1 -> sdb1
            dev_name = os.path.basename(device)
            target_name = dev_name
            
            # Check collision and auto-increment
            counter = 1
            full_path = os.path.join(base_mount_path, target_name)
            while os.path.ismount(full_path) or (os.path.exists(full_path) and os.listdir(full_path)):
                # If mount point exists and is mounted OR exists and is not empty (safety)
                # But prompt specifically said "if there is something mounted there"
                # Checking listdir is safer to avoid mounting over existing data if it's just a folder
                target_name = f"{dev_name}-{counter}"
                full_path = os.path.join(base_mount_path, target_name)
                counter += 1
        else:
            if not mount_name:
                 raise ValueError("mount_name must be provided if automatic is False")
            target_name = mount_name
            full_path = os.path.join(base_mount_path, target_name)
            
            if os.path.ismount(full_path):
                raise ValueError(f"Mount point {target_name} is already in use")

        mount_point = full_path
        
        # Create dir if not exists
        try:
            os.makedirs(mount_point, exist_ok=True)
        except OSError as e:
            raise Exception(f"Failed to create mount point {mount_point}: {e}")
        
        # Mount
        try:
             subprocess.run(["mount", device, mount_point], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
             # Cleanup dir if we created it and it's empty? 
             # Maybe not, unsafe.
             raise Exception(f"Failed to mount {device} to {mount_point}: {e.stderr}")
             
        return mount_point
