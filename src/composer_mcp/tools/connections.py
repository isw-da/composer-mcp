"""Connection management — data warehouse / database connections."""

from __future__ import annotations

from typing import Any
from ..client import ComposerClient


async def list_connection_types(client: ComposerClient) -> list[dict]:
    """Return the connector types registered with this Composer instance.
    Each item has id, name, subStorageType.
    """
    items = await client.get_list("/connection/types")
    return [
        {
            "id": c["id"],
            "name": c.get("name"),
            "subStorageType": c.get("subStorageType"),
        }
        for c in items
        if isinstance(c, dict)
    ]


async def get_connection_type(client: ComposerClient, type_id: str) -> dict:
    """Get full schema (parameters list) for a connector type.
    Useful before creating a connection to know which params are required.
    """
    return await client.get(f"/connection/types/{type_id}")


async def list_connections(client: ComposerClient) -> list[dict]:
    """List all data connections in the instance."""
    items = await client.get_list("/connections")
    return [
        {
            "id": c["id"],
            "name": c.get("name"),
            "subStorageType": c.get("subStorageType"),
            "connectionTypeId": c.get("connectionTypeId"),
            "disabled": c.get("disabled", False),
        }
        for c in items
        if isinstance(c, dict)
    ]


async def get_connection(client: ComposerClient, connection_id: str) -> dict:
    """Get full connection details (parameters with passwords masked)."""
    return await client.get(f"/connections/{connection_id}")


async def create_connection(
    client: ComposerClient,
    name: str,
    connection_type_id: str,
    sub_storage_type: str,
    parameters: dict[str, str],
) -> dict:
    """Create a new data connection.
    parameters maps API param keys to values, e.g.
      {"JDBC_URL": "...", "USER_NAME": "...", "PASSWORD": "..."}
    See get_connection_type to discover required params per connector type.
    """
    body = {
        "name": name,
        "type": "EDC2",
        "connectionTypeId": connection_type_id,
        "subStorageType": sub_storage_type,
        "allParameters": [
            {"key": k, "value": v, "systemAccess": False}
            for k, v in parameters.items()
        ],
    }
    return await client.post("/connections", body)


async def delete_connection(client: ComposerClient, connection_id: str) -> dict:
    await client.delete(f"/connections/{connection_id}")
    return {"deleted": connection_id}


# ----------------------------------------------------------------------
# Per-provider convenience helpers
#
# Composer's create_connection takes a free-form parameters dict, which is
# flexible but means every caller has to look up the right keys. These
# helpers wrap the common providers with the parameter shapes we've
# verified against UAT.
#
# Connection type ids and sub-storage types are stable per Composer build
# but technically derived from the catalogue. Run `list_connection_types`
# if any of these stop working after a Composer upgrade.
# ----------------------------------------------------------------------


# Provider catalogue snapshot (Composer v25). Use list_connection_types if
# this drifts out of date.
PROVIDERS = {
    "snowflake": {
        "connectionTypeId": "snowflake",
        "subStorageType": "SNOWFLAKE",
        "required": ["JDBC_URL", "USER_NAME", "PASSWORD"],
    },
    "bigquery": {
        "connectionTypeId": "bigquery",
        "subStorageType": "BIGQUERY",
        "required": ["PROJECT_ID", "OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET"],
        "auth_modes": ["oauth_web", "service_account_json"],
    },
    "postgres": {
        "connectionTypeId": "postgres",
        "subStorageType": "POSTGRES",
        "required": ["JDBC_URL", "USER_NAME", "PASSWORD"],
    },
    "redshift": {
        "connectionTypeId": "redshift",
        "subStorageType": "REDSHIFT",
        "required": ["JDBC_URL", "USER_NAME", "PASSWORD"],
    },
    "databricks": {
        "connectionTypeId": "databricks",
        "subStorageType": "DATABRICKS",
        "required": ["JDBC_URL", "PASSWORD"],
    },
    "sqlserver": {
        "connectionTypeId": "sqlserver",
        "subStorageType": "SQLSERVER",
        "required": ["JDBC_URL", "USER_NAME", "PASSWORD"],
    },
    "mysql": {
        "connectionTypeId": "mysql",
        "subStorageType": "MYSQL",
        "required": ["JDBC_URL", "USER_NAME", "PASSWORD"],
    },
}


async def create_snowflake_connection(
    client: ComposerClient,
    name: str,
    account: str,
    warehouse: str,
    database: str,
    schema: str,
    user: str,
    password: str,
    role: str | None = None,
) -> dict:
    """Create a Snowflake connection.

    `account` is the Snowflake account locator, e.g. `xy12345.eu-west-1.aws`.
    Composer assembles the JDBC URL for you.
    """
    jdbc = (
        f"jdbc:snowflake://{account}.snowflakecomputing.com/"
        f"?warehouse={warehouse}&db={database}&schema={schema}"
        + (f"&role={role}" if role else "")
    )
    return await create_connection(
        client,
        name,
        connection_type_id=PROVIDERS["snowflake"]["connectionTypeId"],
        sub_storage_type=PROVIDERS["snowflake"]["subStorageType"],
        parameters={"JDBC_URL": jdbc, "USER_NAME": user, "PASSWORD": password},
    )


async def create_bigquery_oauth_connection(
    client: ComposerClient,
    name: str,
    project_id: str,
    oauth_web_client_id: str,
    oauth_web_client_secret: str,
    dataset: str | None = None,
) -> dict:
    """Create a BigQuery connection using OAuth (web client).

    CRITICAL: this MUST be a Web OAuth client, not a Desktop client.
    Desktop clients only allow `http://localhost` redirect URIs which
    Composer's OAuth callback can't satisfy. Symptom of using a Desktop
    client: OAuth flow hangs on "Connecting…" indefinitely.

    Composer renders an OAuth flow on first connect; the user authorises
    in their Google account and the refresh token is stored encrypted on
    the connection record. Use `create_bigquery_service_account_connection`
    for headless setups instead.

    `project_id` is the GCP project (e.g. `agile-tracker-403309`).
    `dataset` is optional but lets you scope the connection at create time.
    """
    params = {
        "PROJECT_ID": project_id,
        "OAUTH_CLIENT_ID": oauth_web_client_id,
        "OAUTH_CLIENT_SECRET": oauth_web_client_secret,
    }
    if dataset:
        params["DEFAULT_DATASET"] = dataset
    return await create_connection(
        client,
        name,
        connection_type_id=PROVIDERS["bigquery"]["connectionTypeId"],
        sub_storage_type=PROVIDERS["bigquery"]["subStorageType"],
        parameters=params,
    )


async def create_bigquery_service_account_connection(
    client: ComposerClient,
    name: str,
    project_id: str,
    service_account_json: str,
    dataset: str | None = None,
) -> dict:
    """Create a BigQuery connection using a Service Account JSON key.

    Headless authentication path — no OAuth click-through. Pass the FULL
    JSON contents (not the file path); Composer encrypts it server-side.
    Note: in pod-deployed Composer, the JSON has to land on the pod
    filesystem first via KEY_PATH; from the API side, Composer accepts the
    JSON inline and writes it to its key store.
    """
    params = {
        "PROJECT_ID": project_id,
        "SERVICE_ACCOUNT_JSON": service_account_json,
    }
    if dataset:
        params["DEFAULT_DATASET"] = dataset
    return await create_connection(
        client,
        name,
        connection_type_id=PROVIDERS["bigquery"]["connectionTypeId"],
        sub_storage_type=PROVIDERS["bigquery"]["subStorageType"],
        parameters=params,
    )


async def create_postgres_connection(
    client: ComposerClient,
    name: str,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    ssl_mode: str = "require",
) -> dict:
    """Create a Postgres connection. `ssl_mode` defaults to require for
    cloud Postgres (Supabase, Neon, RDS); use 'disable' for local dev only."""
    jdbc = f"jdbc:postgresql://{host}:{port}/{database}?sslmode={ssl_mode}"
    return await create_connection(
        client,
        name,
        connection_type_id=PROVIDERS["postgres"]["connectionTypeId"],
        sub_storage_type=PROVIDERS["postgres"]["subStorageType"],
        parameters={"JDBC_URL": jdbc, "USER_NAME": user, "PASSWORD": password},
    )


async def create_databricks_connection(
    client: ComposerClient,
    name: str,
    host: str,
    http_path: str,
    token: str,
    catalog: str | None = None,
    schema: str | None = None,
) -> dict:
    """Create a Databricks SQL Warehouse connection.

    `host` is the workspace hostname, e.g. `dbc-12345-abcd.cloud.databricks.com`.
    `http_path` is the SQL Warehouse HTTP path, e.g. `/sql/1.0/warehouses/abcdef`.
    `token` is a Databricks personal access token (acts as both user and password).
    """
    jdbc_parts = [
        f"jdbc:databricks://{host}:443",
        f"httpPath={http_path}",
        "AuthMech=3",
        "UID=token",
    ]
    if catalog:
        jdbc_parts.append(f"ConnCatalog={catalog}")
    if schema:
        jdbc_parts.append(f"ConnSchema={schema}")
    jdbc = ";".join(jdbc_parts)
    return await create_connection(
        client,
        name,
        connection_type_id=PROVIDERS["databricks"]["connectionTypeId"],
        sub_storage_type=PROVIDERS["databricks"]["subStorageType"],
        parameters={"JDBC_URL": jdbc, "PASSWORD": token},
    )


async def test_connection(client: ComposerClient, connection_id: str) -> dict:
    """Ask Composer to attempt a live connection test.

    Returns whatever Composer reports — usually `{ok: true}` or an error
    object with the underlying JDBC/connector failure. For OAuth-based
    connections, `ok: false` with "OAuth required" means the user hasn't
    completed the auth flow yet — open the connection in the UI to
    trigger it.
    """
    try:
        return await client.post(f"/connections/{connection_id}/test", {})
    except Exception as e:
        # Some Composer builds expose this as GET; fall back.
        return {"ok": False, "error": str(e)[:300]}
