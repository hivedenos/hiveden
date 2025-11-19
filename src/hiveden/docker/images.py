import docker
from docker.errors import ImageNotFound

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
