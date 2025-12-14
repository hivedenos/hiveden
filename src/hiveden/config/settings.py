import os

class Config:
    app_directory = os.getenv("HIVEDEN_APP_DIRECTORY", "/shares/apps")
    movies_directory = os.getenv("HIVEDEN_MOVIES_DIRECTORY", "/shares/movies")
    tvshows_directory = os.getenv("HIVEDEN_TVSHOWS_DIRECTORY", "/share/tvshows")
    backup_directory = os.getenv("HIVEDEN_BACKUP_DIRECTORY", "/shares/backups")
    docker_network_name = os.getenv("HIVEDEN_DOCKER_NETWORK_NAME", "hiveden-net")

config = Config()