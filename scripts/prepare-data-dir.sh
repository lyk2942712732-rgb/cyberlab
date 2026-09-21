#!/bin/sh
set -eu
# Run once as root on the Linux server. UID matches the unprivileged backend.
install -d -m 0750 -o 10001 -g 10001 /var/lib/cyberlab
install -d -m 0750 -o 10001 -g 10001 /var/lib/cyberlab/uploads
install -d -m 0750 -o 10001 -g 10001 /var/lib/cyberlab/uploads/target-images
install -d -m 0750 -o 10001 -g 10001 /var/lib/cyberlab/workspaces
install -d -m 0750 -o 10001 -g 10001 /var/lib/cyberlab/logs
printf '%s\n' 'Prepared /var/lib/cyberlab. Docker image storage remains managed by Docker Engine.'
