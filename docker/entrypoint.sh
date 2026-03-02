#!/bin/bash

PUID=${PUID:-99}
PGID=${PGID:-100}

echo "Using PUID=$PUID PGID=$PGID"

# Create group if needed
if ! getent group transcodr > /dev/null; then
    groupadd -g "$PGID" transcodr
else
    groupmod -o -g "$PGID" transcodr
fi

# Create user if needed
if ! id transcodr > /dev/null 2>&1; then
    useradd -o -u "$PUID" -g "$PGID" -m transcodr
else
    usermod -o -u "$PUID" -g "$PGID" transcodr
fi

# Fix ownership of mounted folders
chown -R "$PUID:$PGID" /config 2>/dev/null || true
chown -R "$PUID:$PGID" /media 2>/dev/null || true
chown -R "$PUID:$PGID" /temp 2>/dev/null || true

# Drop privileges and run the daemon
exec gosu transcodr "$@"
