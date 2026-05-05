#!/usr/bin/env bash
set -euo pipefail

kubectl rollout restart deployment/infrarouter -n infrarouter
