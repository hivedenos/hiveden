import docker
from docker.errors import ImageNotFound
from typing import List, Dict, Any

client = docker.from_env()

def image_exists(image_name: str) -> bool:
    """Check if a Docker image exists locally."""
    try:
        client.images.get(image_name)
        return True
    except ImageNotFound:
        return False

def pull_image(image_name: str):
    """Pull a Docker image from a registry."""
    try:
        return client.images.pull(image_name)
    except ImageNotFound:
        raise

class DockerImageManager:
    def __init__(self):
        self.client = client

    def list_images(self) -> List[Any]:
        """List all local images."""
        return self.client.images.list()

    def get_image(self, image_id: str) -> Any:
        """Get an image by ID or name."""
        return self.client.images.get(image_id)

    def get_image_layers(self, image_id: str) -> List[Dict[str, Any]]:
        """Get the history (layers) of an image."""
        image = self.client.images.get(image_id)
        return image.history()

    def delete_image(self, image_id: str):
        """Delete an image."""
        self.client.images.remove(image_id)

    