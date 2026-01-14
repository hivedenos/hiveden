# Tech Stack

## Core Technologies
- **Language:** Python 3.7+
- **CLI Framework:** [Click](https://click.palletsprojects.com/) - Used for creating the command-line interface.
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) with [Uvicorn](https://www.uvicorn.org/) - Used for the REST API.

## Infrastructure & Management
- **Containerization:** 
    - [Docker](https://www.docker.com/) (via `docker-py`) - For managing Docker containers and networks.
    - [LXC](https://linuxcontainers.org/) (via `lxc-python3`) - For managing LXC containers.
- **System Monitoring:** [psutil](https://github.com/giampaolo/psutil) - Used for retrieving hardware and OS information.
- **Configuration:** [PyYAML](https://pyyaml.org/) - For parsing the `config.yaml` file.

## Data & Storage
- **Database:** 
    - [PostgreSQL](https://www.postgresql.org/) (via `psycopg2`) - For persistent storage.
    - [SQLite](https://www.sqlite.org/) - For lightweight/default database usage.
- **Migrations:** [yoyo-migrations](https://ollycope.com/software/yoyo/) - For database schema management.

## Integrations
- **DNS/Ad-blocking:** [Pi-hole](https://pi-hole.net/) (via `pihole6api`) - For managing Pi-hole instances.
