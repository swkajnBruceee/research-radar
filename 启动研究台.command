#!/bin/zsh
set -eu
cd -- "$(dirname "$0")"
if ! curl -fsS --max-time 2 http://127.0.0.1:8765/api/discovery > /dev/null 2>&1; then
    python3 scripts/manage_service.py install
    for RADAR_ATTEMPT in 1 2 3 4 5; do
        if curl -fsS --max-time 2 http://127.0.0.1:8765/api/discovery > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi
open http://127.0.0.1:8765/
