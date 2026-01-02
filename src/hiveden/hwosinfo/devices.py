import json
import subprocess
import shutil
from typing import List, Dict, Any, Optional
from hiveden.hwosinfo.models import SystemDevices, GenericDevice
from hiveden.storage.devices import get_system_disks

def get_lshw_data() -> List[Dict[str, Any]]:
    """
    Executes lshw -json and returns the parsed data.
    Returns a list because lshw sometimes returns a list of nodes.
    """
    if not shutil.which("lshw"):
        return []

    try:
        # -json for JSON output
        # -notime to avoid changing timestamps? No, not needed.
        # -quiet to suppress progress
        cmd = ["lshw", "-json", "-quiet"]
        output = subprocess.check_output(cmd).decode()
        # lshw json output can sometimes be invalid if multiple roots? 
        # Usually it's a single object or a list.
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                return [data]
            return data
        except json.JSONDecodeError:
            # Fallback for weird lshw output (sometimes it outputs multiple json objects concatenated)
            # We can try to wrap it in []
            try:
                data = json.loads(f"[{output.replace('}{', '},{')}]")
                return data
            except:
                return []
    except Exception:
        return []

def extract_devices(node: Dict[str, Any], categories: Dict[str, List[GenericDevice]]):
    """
    Recursively traverse lshw tree and populate categories.
    """
    device_class = node.get("class")
    bus_info = node.get("businfo", "")
    
    # Map lshw class to our categories
    target_list = None
    
    # Prepare fields that might be lists
    logical_name = node.get("logicalname")
    if isinstance(logical_name, list):
        logical_name = ", ".join([str(x) for x in logical_name])
    
    # Create GenericDevice object
    device = GenericDevice(
        id=node.get("id", ""),
        name=node.get("product", node.get("name", "Unknown")),
        vendor=node.get("vendor"),
        product=node.get("product"),
        description=node.get("description"),
        driver=node.get("configuration", {}).get("driver"),
        bus_info=bus_info,
        logical_name=logical_name,
        version=node.get("version"),
        serial=node.get("serial"),
        capacity=node.get("capacity"),
        clock=node.get("clock"),
        capabilities=node.get("capabilities"),
        configuration=node.get("configuration")
    )

    is_usb_device = "usb@" in bus_info or str(node.get("physid", "")).startswith("usb")
    
    if device_class == "display":
        target_list = categories["video"]
    elif device_class == "network":
        target_list = categories["network"]
    elif device_class == "multimedia":
        target_list = categories["multimedia"]
    elif is_usb_device and device_class != "bus": 
        # It's a USB device, and not a bus controller/hub (usually hubs are class 'bus')
        # However, root hubs are class bus. External hubs might be class bus.
        # We want user facing endpoints (Input, Camera, Mass Storage, etc.)
        # If it's a generic USB device (like a keyboard), it typically has class 'input' or 'generic'.
        # We add it to 'usb' list.
        target_list = categories["usb"]
    elif device_class == "generic" and is_usb_device:
        target_list = categories["usb"]
    elif device_class == "input":
        # Inputs are interesting, often USB
        if is_usb_device:
            target_list = categories["usb"]
        else:
            target_list = categories["other"]
    
    # Add to list if matched
    if target_list is not None:
        target_list.append(device)
    
    # Recurse
    children = node.get("children", [])
    for child in children:
        # lshw children can be a list or sometimes None
        if child:
            extract_devices(child, categories)

def get_all_devices() -> SystemDevices:
    """
    Aggregates all system devices.
    """
    # 1. Get Storage from hiveden existing logic
    storage_disks = get_system_disks()
    
    # 2. Get LSHW data
    lshw_data = get_lshw_data()
    
    categories = {
        "video": [],
        "network": [],
        "multimedia": [],
        "usb": [],
        "other": []
    }
    
    for root in lshw_data:
        extract_devices(root, categories)
        
    # Deduplication might be needed if multiple passes catch same device?
    # Our recursion is tree-based, so each node visited once. 
    # But a device might match "usb" criteria and "video" criteria?
    # Logic above uses if/elif, so exclusive.
    
    # Filter out empty names or useless entries
    for key in categories:
        categories[key] = [d for d in categories[key] if d.name and d.name != "Unknown"]

    summary = {
        "count_storage": len(storage_disks),
        "count_video": len(categories["video"]),
        "count_usb": len(categories["usb"]),
        "count_network": len(categories["network"]),
        "count_multimedia": len(categories["multimedia"]),
    }

    return SystemDevices(
        summary=summary,
        storage=storage_disks,
        video=categories["video"],
        usb=categories["usb"],
        network=categories["network"],
        multimedia=categories["multimedia"],
        other=categories["other"]
    )
