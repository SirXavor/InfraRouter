#!/usr/bin/env bash
set -euo pipefail

./scripts/build.sh
./scripts/push.sh
./scripts/restart.sh
