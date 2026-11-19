#!/usr/bin/env bash
# Deploys one service to Azure Container Apps. Called by the CD job in .github/workflows/ci.yml.
# The first run creates the container app; later runs update it to the new image.
#
# Usage: infra/deploy.sh <service> <image> [KEY=VALUE ...]   (extra plain environment variables)
# Environment:
#   DB_PASSWORD      password of <service>_user (from a GitHub secret)
#   GHCR_PULL_TOKEN  optional; a token with read:packages, needed only if the GHCR package is private
#   GHCR_USER        GitHub user that owns GHCR_PULL_TOKEN
# Prints the app's public https URL on stdout; everything else goes to stderr.

set -euo pipefail

PREFIX="nmedic-ieu2024"
RG="rg-nmedic"
ACA_ENV="${PREFIX}-env"
SQL_FQDN="${PREFIX}-sql.database.windows.net"

service="$1"; image="$2"; shift 2
app="${PREFIX}-${service}"
: "${DB_PASSWORD:?DB_PASSWORD is not set}"

# The connection string is stored as a Container Apps secret, never as a plain env var.
db_url="mssql://${service}_user:${DB_PASSWORD}@${SQL_FQDN}:1433/${PREFIX}-${service}-db"

registry_args=()
if [ -n "${GHCR_PULL_TOKEN:-}" ]; then
  registry_args=(--registry-server ghcr.io --registry-username "${GHCR_USER:?GHCR_USER is not set}" --registry-password "$GHCR_PULL_TOKEN")
fi

if az containerapp show -g "$RG" -n "$app" -o none 2>/dev/null; then
  echo "Updating ${app} to ${image}" >&2
  az containerapp secret set -g "$RG" -n "$app" --secrets "database-url=${db_url}" -o none >&2
  if [ -n "${GHCR_PULL_TOKEN:-}" ]; then
    az containerapp registry set -g "$RG" -n "$app" --server ghcr.io \
      --username "$GHCR_USER" --password "$GHCR_PULL_TOKEN" -o none >&2
  fi
  az containerapp update -g "$RG" -n "$app" --image "$image" \
    --min-replicas 0 --max-replicas 1 \
    --set-env-vars "DATABASE_URL=secretref:database-url" "$@" -o none >&2
else
  echo "Creating ${app} from ${image}" >&2
  az containerapp create -g "$RG" -n "$app" --environment "$ACA_ENV" --image "$image" \
    --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
    --secrets "database-url=${db_url}" \
    --env-vars "DATABASE_URL=secretref:database-url" "$@" \
    ${registry_args[@]+"${registry_args[@]}"} -o none >&2
fi

echo "https://$(az containerapp show -g "$RG" -n "$app" --query properties.configuration.ingress.fqdn -o tsv)"
