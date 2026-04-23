#!/bin/bash

#installing CloudNativePG
echo "Installing CloudNativePG operator..."
kubectl apply --server-side -f \
  https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.29/releases/cnpg-1.29.0.yaml
