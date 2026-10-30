#!/usr/bin/env bash
set -euo pipefail
helm install eg oci://docker.io/envoyproxy/gateway-helm --version 1.9.3 \
  -n envoy-gateway-system --create-namespace --wait --timeout 5m
kubectl apply -f "$(dirname "$0")/../k8s/gateway.yaml"
kubectl wait --for=condition=Programmed gateway/web -n app --timeout=120s
