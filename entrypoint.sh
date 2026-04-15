#!/bin/sh
# ---------------------------------------------------------------------------
# entrypoint.sh — run the app as the UID/GID specified by PUID/PGID env vars.
#
# This lets NAS deployments match the container user to the filesystem owner
# of the bind-mounted /data directory, avoiding permission denied errors.
#
# Defaults to UID 1000 / GID 1000 if the env vars are not set.
# ---------------------------------------------------------------------------
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Create a group with the requested GID if it doesn't already exist.
if ! getent group "$PGID" > /dev/null 2>&1; then
    groupadd -g "$PGID" appgroup
fi

# Create a user with the requested UID/GID if it doesn't already exist.
if ! getent passwd "$PUID" > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -M -s /bin/sh appuser
fi

# Ensure /data is writable by the target user.
chown -R "$PUID:$PGID" /data

# Drop from root to the target UID/GID and exec the real process.
exec gosu "$PUID:$PGID" "$@"
