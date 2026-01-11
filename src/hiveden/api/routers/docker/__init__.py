from fastapi import APIRouter
from hiveden.api.routers.docker import containers, images

router = APIRouter(prefix="/docker")

# Include container routes directly
router.include_router(containers.router)

# Include image routes
router.include_router(images.router)
