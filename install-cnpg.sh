#!/usr/bin/env bash
# Install the CloudNativePG operator on the cluster.
# Prereq: kubectl is pointed at the EKS cluster (see README → "Connect").

set -euo pipefail

CNPG_VERSION="${CNPG_VERSION:-1.29.0}"
MANIFEST="https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-${CNPG_VERSION%.*}/releases/cnpg-${CNPG_VERSION}.yaml"

echo "Installing CloudNativePG operator (${CNPG_VERSION})..."
kubectl apply --server-side -f "${MANIFEST}"

echo "Waiting for operator to be ready..."
kubectl -n cnpg-system rollout status deploy/cnpg-controller-manager --timeout=180s
echo "CloudNativePG ready."
