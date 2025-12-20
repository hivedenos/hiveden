import os

class Config:
    app_directory = os.getenv("HIVEDEN_APP_DIRECTORY", "/shares/apps")
    movies_directory = os.getenv("HIVEDEN_MOVIES_DIRECTORY", "/shares/movies")
    tvshows_directory = os.getenv("HIVEDEN_TVSHOWS_DIRECTORY", "/share/tvshows")
    backup_directory = os.getenv("HIVEDEN_BACKUP_DIRECTORY", "/shares/backups")
    docker_network_name = os.getenv("HIVEDEN_DOCKER_NETWORK_NAME", "hiveden-net")
    domain = os.getenv("HIVEDEN_DOMAIN", "hiveden.local")

    # Pi-hole Configuration
    pihole_enabled = os.getenv("HIVEDEN_PIHOLE_ENABLED", "false").lower() == "true"
    pihole_host = os.getenv("HIVEDEN_PIHOLE_HOST", "http://pi.hole")
    pihole_password = os.getenv("HIVEDEN_PIHOLE_PASSWORD", "")

config = Config()