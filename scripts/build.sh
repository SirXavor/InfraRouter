#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-xavor}"
TAG="${TAG:-latest}"

echo "Building InfraRouter API image..."
docker build -t ${REGISTRY}/infrarouter-api:${TAG} ./src/api

echo "Done."
echo "${REGISTRY}/infrarouter-api:${TAG}"
