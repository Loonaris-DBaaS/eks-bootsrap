#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="${SCRIPT_DIR}/networkpolicies-template.yaml"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "Error: kubectl is required but not found in PATH." >&2
  exit 1
fi

if ! command -v envsubst >/dev/null 2>&1; then
  echo "Error: envsubst is required (package: gettext)." >&2
  exit 1
fi

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo "Error: template file not found: ${TEMPLATE_FILE}" >&2
  exit 1
fi

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 tenant-1 [tenant-2 tenant-3 ...]" >&2
  exit 1
fi

for tenant in "$@"; do
  echo "Applying tenant policies for namespace: ${tenant}"
  TENANT_NS="${tenant}" envsubst < "${TEMPLATE_FILE}" | kubectl apply -f -
done

echo "All tenant policies applied successfully."
