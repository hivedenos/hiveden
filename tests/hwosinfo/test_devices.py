from hiveden.hwosinfo.devices import extract_devices
from hiveden.hwosinfo.models import GenericDevice

def test_extract_devices_logical_name_list():
    """Test that extract_devices correctly handles logical_name as a list."""
    categories = {
        "video": [],
        "network": [],
        "multimedia": [],
        "usb": [],
        "other": []
    }
    
    # Mock data resembling lshw output with list logical_name
    node = {
        "id": "test_device",
        "class": "network",
        "logicalname": ["eth0", "test_alias"],
        "product": "Test Network Card"
    }
    
    extract_devices(node, categories)
    
    assert len(categories["network"]) == 1
    device = categories["network"][0]
    assert device.logical_name == "eth0, test_alias"
    assert device.name == "Test Network Card"

def test_extract_devices_logical_name_string():
    """Test that extract_devices correctly handles logical_name as a string."""
    categories = {
        "video": [],
        "network": [],
        "multimedia": [],
        "usb": [],
        "other": []
    }
    
    node = {
        "id": "test_device_2",
        "class": "display",
        "logicalname": "/dev/video0",
        "product": "Test Webcam"
    }
    
    extract_devices(node, categories)
    
    assert len(categories["video"]) == 1
    device = categories["video"][0]
    assert device.logical_name == "/dev/video0"
