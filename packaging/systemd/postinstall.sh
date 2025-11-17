#!/bin/sh

# Create the hiveden-api user and group if they don't exist
if ! id -u hiveden-api >/dev/null 2>&1; then
    useradd -r -s /bin/false hiveden-api
fi

# Create the working directory
mkdir -p /var/lib/hiveden-api
chown -R hiveden-api:hiveden-api /var/lib/hiveden-api

# Enable and start the service
systemctl enable hiveden-api.service
systemctl start hiveden-api.service
