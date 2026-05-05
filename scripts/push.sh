#!/usr/bin/env bash
set -euo pipefail

REGISTRY="${REGISTRY:-xavor}"
TAG="${TAG:-latest}"

echo "Pushing InfraRouter API image..."
docker push ${REGISTRY}/infrarouter-api:${TAG}

echo "Push complete."
