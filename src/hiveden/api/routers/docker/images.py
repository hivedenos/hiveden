import traceback
from fastapi import APIRouter, HTTPException
from fastapi.logger import logger
from fastapi.responses import JSONResponse
from docker.errors import ImageNotFound, APIError

from hiveden.api.dtos import (
    BaseResponse,
    ErrorResponse,
    ImageListResponse,
    ImageLayerListResponse,
    DockerImage,
    ImageLayer
)
from hiveden.docker.images import DockerImageManager

router = APIRouter(tags=["Docker Images"])

@router.delete("/images/{image_id:path}", response_model=BaseResponse)
def delete_image(image_id: str):
    """
    Delete a Docker image.
    Does not support forced removal.
    """
    try:
        manager = DockerImageManager()
        manager.delete_image(image_id)
        return BaseResponse(status="success", message=f"Image {image_id} deleted successfully.")
    except ImageNotFound:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(message="Image not found").model_dump()
        )
    except APIError as e:
        if e.status_code == 409:
            return JSONResponse(
                status_code=409,
                content=ErrorResponse(message=f"Cannot delete image: {e.explanation}").model_dump()
            )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )
    except Exception as e:
        logger.error(f"Error deleting image {image_id}: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

@router.get("/images", response_model=ImageListResponse)
def list_images():
    """List all Docker images."""
    try:
        manager = DockerImageManager()
        images = manager.list_images()
        
        data = []
        for img in images:
            # attrs['Created'] is usually an int timestamp or ISO string depending on docker version/api
            # Docker SDK usually returns Image objects.
            data.append(DockerImage(
                id=img.id,
                tags=img.tags,
                created=str(img.attrs.get('Created', '')),
                size=img.attrs.get('Size', 0),
                labels=img.labels
            ))
            
        return ImageListResponse(data=data)
    except Exception as e:
        logger.error(f"Error listing images: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )

@router.get("/images/{image_id:path}/layers", response_model=ImageLayerListResponse)
def get_image_layers(image_id: str):
    """
    Get layers (history) of a Docker image.
    Note: image_id might contain slashes if it's a repo/name:tag, so use :path.
    """
    try:
        manager = DockerImageManager()
        layers = manager.get_image_layers(image_id)
        
        data = []
        for layer in layers:
            data.append(ImageLayer(
                id=layer.get('Id', 'missing'),
                created=layer.get('Created', 0),
                created_by=layer.get('CreatedBy', ''),
                size=layer.get('Size', 0),
                comment=layer.get('Comment', ''),
                tags=layer.get('Tags')
            ))
            
        return ImageLayerListResponse(data=data)
    except Exception as e:
        logger.error(f"Error getting image layers {image_id}: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(message=str(e)).model_dump()
        )
