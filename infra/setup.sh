#!/usr/bin/env bash
# One-time Azure setup for OrbitWatch.
#
# Creates, inside the resource group (never creates or deletes the group):
#   - 1 SQL logical server            ${PREFIX}-sql            (LOCATION)
#   - 2 serverless databases          ${PREFIX}-catalog-db, ${PREFIX}-propagation-db
#   - 1 contained user per database   catalog_user, propagation_user (db_owner of their own DB only)
#   - 1 Container Apps environment    ${PREFIX}-env            (LOCATION, Consumption only)
#     Azure also creates a Log Analytics workspace for it (container logs, free up to 5 GB/month).
#   - 1 storage account for the UI    ${UI_STORAGE}            (LOCATION, static website, Standard LRS)
#   - 1 managed identity for CI/CD    ${PREFIX}-github         (Contributor on the resource group only;
#     GitHub Actions on main signs in as it through a federated credential, so there is no password)
# The Container Apps themselves are created by the CI/CD pipeline, not here.
#
# Secrets are read from the environment only; nothing secret is stored in this file:
#   SQL_ADMIN_PASSWORD, CATALOG_DB_PASSWORD, PROPAGATION_DB_PASSWORD
# Generate them in your shell, for example:
#   export SQL_ADMIN_PASSWORD="Ow_$(openssl rand -hex 16)_A1"
#
# Usage: infra/setup.sh <step>
#   steps: extension | sql-server | databases | db-users | verify-isolation | env | ui-storage | github-identity | all
# Optional: AZURE_SUBSCRIPTION (name or id) to select the subscription first.

set -euo pipefail

PREFIX="nmedic-ieu2024"
RG="rg-nmedic"
LOCATION="spaincentral"   # allowed by the subscription's region policy
SQL_ADMIN_USER="orbitadmin"

SQL_SERVER="${PREFIX}-sql"
CATALOG_DB="${PREFIX}-catalog-db"
PROPAGATION_DB="${PREFIX}-propagation-db"
ACA_ENV="${PREFIX}-env"
UI_STORAGE="${PREFIX//-/}ui"   # storage names allow no hyphens: nmedicieu2024ui
GITHUB_IDENTITY="${PREFIX}-github"
# GitHub's OIDC subject includes the owner and repo IDs:
#   gh api repos/neo0oo/OrbitWatch --jq '"repo:\(.owner.login)@\(.owner.id)/\(.name)@\(.id)"'
GITHUB_OIDC_SUBJECT="repo:neo0oo@178232820/OrbitWatch@1394910778:ref:refs/heads/main"
AUTO_PAUSE_DELAY="${AUTO_PAUSE_DELAY:-15}"   # minutes; Azure's minimum for serverless is 15
SQLCMD_IMAGE="mcr.microsoft.com/mssql/server:2022-latest"
TEMP_RULE="setup-temp"

require() {
  for v in "$@"; do
    if [ -z "${!v:-}" ]; then echo "Missing environment variable: $v" >&2; exit 1; fi
  done
}

if [ -n "${AZURE_SUBSCRIPTION:-}" ]; then
  az account set --subscription "$AZURE_SUBSCRIPTION"
fi

fqdn() { echo "${SQL_SERVER}.database.windows.net"; }

# Run sqlcmd from the SQL Server image. The login password is passed as SQLCMDPASSWORD
# and any extra variables by name only (-e NAME), so no secret appears on a command line.
# sqlcmd exposes environment variables as $(NAME) scripting variables.
sqlcmd_run() {
  local user="$1" password_var="$2" db="$3" query="$4"; shift 4
  local env_args=() v
  for v in "$@"; do env_args+=(-e "$v"); done
  SQLCMDPASSWORD="${!password_var}" docker run --rm --platform linux/amd64 \
    -e SQLCMDPASSWORD ${env_args[@]+"${env_args[@]}"} \
    --entrypoint /opt/mssql-tools18/bin/sqlcmd "$SQLCMD_IMAGE" \
    -S "tcp:$(fqdn),1433" -d "$db" -U "$user" -N -b -l 30 -Q "$query"
}

set_temp_ip_rule() {
  echo "Setting temporary firewall rule ${TEMP_RULE} to $1"
  az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n "$TEMP_RULE" \
    --start-ip-address "$1" --end-ip-address "$1" -o none
}

# Adds a single-address rule for this machine, then probes with sqlcmd ($1 user, $2 password
# var, $3 database). Some networks leave through several public IPs, so if Azure reports a
# different client IP than api.ipify.org, the rule is moved to the IP Azure reports.
add_temp_ip_rule() {
  local ip reported out attempt
  ip="$(curl -fsS https://api.ipify.org)"
  set_temp_ip_rule "$ip"
  for attempt in 1 2 3 4; do
    if out="$(sqlcmd_run "$1" "$2" "$3" "SELECT 1" 2>&1)"; then
      echo "Connected from ${ip}"; return 0
    fi
    reported="$(echo "$out" | sed -n "s/.*Client with IP address '\([0-9.]*\)'.*/\1/p" | head -1)"
    if [ -z "$reported" ]; then echo "$out" >&2; return 1; fi
    if [ "$reported" != "$ip" ]; then
      echo "Azure sees this client as ${reported}, not ${ip}"
      ip="$reported"; set_temp_ip_rule "$ip"
    fi
    echo "Waiting 20s for the firewall rule to take effect (attempt ${attempt}/4)"
    sleep 20
  done
  echo "$out" >&2; return 1
}

remove_temp_ip_rule() {
  echo "Removing temporary firewall rule ${TEMP_RULE}"
  az sql server firewall-rule delete -g "$RG" -s "$SQL_SERVER" -n "$TEMP_RULE" -o none || true
}

step_extension() {
  az extension add --name containerapp --upgrade -o none
  # A new subscription must enable each service once before using it (free, creates nothing).
  local ns
  for ns in Microsoft.Sql Microsoft.App Microsoft.OperationalInsights Microsoft.Storage Microsoft.ManagedIdentity; do
    az provider register --namespace "$ns" --wait
  done
}

step_sql_server() {
  require SQL_ADMIN_PASSWORD
  az sql server create -g "$RG" -n "$SQL_SERVER" -l "$LOCATION" \
    --admin-user "$SQL_ADMIN_USER" --admin-password "$SQL_ADMIN_PASSWORD" \
    --query "{name:name, location:location, fqdn:fullyQualifiedDomainName}" -o table
  az sql server firewall-rule create -g "$RG" -s "$SQL_SERVER" -n AllowAzureServices \
    --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 -o table
}

step_databases() {
  local db
  for db in "$CATALOG_DB" "$PROPAGATION_DB"; do
    az sql db create -g "$RG" -s "$SQL_SERVER" -n "$db" \
      --edition GeneralPurpose --compute-model Serverless --family Gen5 \
      --min-capacity 0.5 --capacity 1 --auto-pause-delay "$AUTO_PAUSE_DELAY" \
      --max-size 2GB --backup-storage-redundancy Local \
      --query "{name:name, sku:currentSku.name, autoPauseDelay:autoPauseDelay, maxSizeBytes:maxSizeBytes}" -o table
  done
}

create_user_sql() {
  # $1 user name, $2 name of the env var holding its password
  cat <<SQL
IF USER_ID('$1') IS NULL
  CREATE USER [$1] WITH PASSWORD = '\$($2)';
ELSE
  ALTER USER [$1] WITH PASSWORD = '\$($2)';
IF IS_ROLEMEMBER('db_owner', '$1') = 0
  ALTER ROLE db_owner ADD MEMBER [$1];
SELECT name, type_desc, authentication_type_desc FROM sys.database_principals WHERE name = '$1';
SQL
}

step_db_users() {
  require SQL_ADMIN_PASSWORD CATALOG_DB_PASSWORD PROPAGATION_DB_PASSWORD
  trap remove_temp_ip_rule EXIT
  add_temp_ip_rule "$SQL_ADMIN_USER" SQL_ADMIN_PASSWORD "$CATALOG_DB"
  sqlcmd_run "$SQL_ADMIN_USER" SQL_ADMIN_PASSWORD "$CATALOG_DB" \
    "$(create_user_sql catalog_user CATALOG_DB_PASSWORD)" CATALOG_DB_PASSWORD
  sqlcmd_run "$SQL_ADMIN_USER" SQL_ADMIN_PASSWORD "$PROPAGATION_DB" \
    "$(create_user_sql propagation_user PROPAGATION_DB_PASSWORD)" PROPAGATION_DB_PASSWORD
  remove_temp_ip_rule
  trap - EXIT
}

try_connect() {
  # $1 user, $2 password var, $3 database; prints CONNECTED or FAILED with sqlcmd's message
  local out
  if out="$(sqlcmd_run "$1" "$2" "$3" "SET NOCOUNT ON; SELECT DB_NAME() AS db, USER_NAME() AS usr;" 2>&1)"; then
    echo "  $1 -> $3: CONNECTED"; echo "$out" | sed 's/^/    /'
    return 0
  else
    echo "  $1 -> $3: FAILED"; echo "$out" | sed 's/^/    /'
    return 1
  fi
}

step_verify_isolation() {
  require CATALOG_DB_PASSWORD PROPAGATION_DB_PASSWORD
  trap remove_temp_ip_rule EXIT
  add_temp_ip_rule catalog_user CATALOG_DB_PASSWORD "$CATALOG_DB"
  local ok=1
  try_connect catalog_user CATALOG_DB_PASSWORD "$CATALOG_DB" || ok=0
  try_connect catalog_user CATALOG_DB_PASSWORD "$PROPAGATION_DB" && ok=0
  try_connect propagation_user PROPAGATION_DB_PASSWORD "$PROPAGATION_DB" || ok=0
  try_connect propagation_user PROPAGATION_DB_PASSWORD "$CATALOG_DB" && ok=0
  remove_temp_ip_rule
  trap - EXIT
  if [ "$ok" = 1 ]; then echo "Isolation OK"; else echo "Isolation check FAILED" >&2; return 1; fi
}

step_env() {
  # Azure creates the Log Analytics workspace for the environment (log-analytics is set
  # explicitly because the CLI default changes to azure-monitor in 2.93.0).
  az containerapp env create -g "$RG" -n "$ACA_ENV" -l "$LOCATION" \
    --enable-workload-profiles false --logs-destination log-analytics \
    --query "{name:name, location:location, state:properties.provisioningState}" -o table
}

step_github_identity() {
  # Students cannot register apps (service principals) in the IE directory, so the pipeline
  # signs in as a user-assigned managed identity instead, using GitHub's OIDC token.
  local principal_id rg_id
  az identity create -g "$RG" -n "$GITHUB_IDENTITY" -l "$LOCATION" \
    --query "{name:name, location:location}" -o table
  principal_id="$(az identity show -g "$RG" -n "$GITHUB_IDENTITY" --query principalId -o tsv)"
  rg_id="$(az group show -n "$RG" --query id -o tsv)"
  if [ "$(az role assignment list --assignee "$principal_id" --scope "$rg_id" --role Contributor --query 'length(@)' -o tsv)" = "0" ]; then
    az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type ServicePrincipal \
      --role Contributor --scope "$rg_id" --query "{role:roleDefinitionName, scope:scope}" -o table
  fi
  az identity federated-credential create -g "$RG" --identity-name "$GITHUB_IDENTITY" -n github-main \
    --issuer https://token.actions.githubusercontent.com \
    --subject "$GITHUB_OIDC_SUBJECT" \
    --audiences api://AzureADTokenExchange --query "{name:name, subject:subject}" -o table
  echo "GitHub secrets for azure/login:"
  echo "  AZURE_CLIENT_ID       $(az identity show -g "$RG" -n "$GITHUB_IDENTITY" --query clientId -o tsv)"
  echo "  AZURE_TENANT_ID       $(az account show --query tenantId -o tsv)"
  echo "  AZURE_SUBSCRIPTION_ID $(az account show --query id -o tsv)"
}

step_ui_storage() {
  # The UI is static files served from the storage account's $web container (static website).
  az storage account create -g "$RG" -n "$UI_STORAGE" -l "$LOCATION" \
    --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false \
    --query "{name:name, location:location, sku:sku.name}" -o table
  az storage blob service-properties update --account-name "$UI_STORAGE" --auth-mode key \
    --static-website --index-document index.html --404-document index.html -o none
  echo "UI URL: $(az storage account show -g "$RG" -n "$UI_STORAGE" --query primaryEndpoints.web -o tsv)"
}

case "${1:-}" in
  extension)        step_extension ;;
  sql-server)       step_sql_server ;;
  databases)        step_databases ;;
  db-users)         step_db_users ;;
  verify-isolation) step_verify_isolation ;;
  env)              step_env ;;
  ui-storage)       step_ui_storage ;;
  github-identity)  step_github_identity ;;
  all)
    step_extension; step_sql_server; step_databases; step_db_users
    step_verify_isolation; step_env; step_ui_storage; step_github_identity ;;
  *) sed -n '2,21p' "$0"; exit 2 ;;
esac
