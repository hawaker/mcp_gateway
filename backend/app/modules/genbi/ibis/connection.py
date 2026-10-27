"""Build ibis ``connectionInfo`` from ``GenbiDatasourceModel`` (tiga-adapted)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from app.modules.genbi.datasource.model import GenbiDatasourceModel
from app.modules.genbi.datasource.types import WREN_TYPES
from app.utils.crypto_util import CryptoUtil

IBIS_CONNECTOR_SLUG: dict[str, str] = {
    "POSTGRES": "postgres",
    "BIG_QUERY": "bigquery",
    "SNOWFLAKE": "snowflake",
    "MYSQL": "mysql",
    "ORACLE": "oracle",
    "MSSQL": "mssql",
    "CLICK_HOUSE": "clickhouse",
    "TRINO": "trino",
    "ATHENA": "athena",
    "REDSHIFT": "redshift",
    "DATABRICKS": "databricks",
}


def ibis_connector_slug(wren_type: str) -> str | None:
    key = (wren_type or "").strip().upper()
    return IBIS_CONNECTOR_SLUG.get(key)


def _dec(cipher: str | None) -> str | None:
    if not cipher:
        return None
    try:
        return CryptoUtil.decrypt(cipher)
    except Exception:  # noqa: BLE001
        return None


def _cfg(source: GenbiDatasourceModel) -> dict[str, Any]:
    return source.config if isinstance(source.config, dict) else {}


def _ibis_port(value: Any, default: int | None = None) -> str | None:
    if value is None or value == "":
        return str(default) if default is not None else None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(int(value))
    text = str(value).strip()
    return text or (str(default) if default is not None else None)


def to_ibis_connection_info(source: GenbiDatasourceModel) -> dict[str, Any] | None:
    """Build ibis ``connectionInfo`` from a GenBI datasource row."""
    wren = (source.wren_type or "").strip().upper()
    if wren not in WREN_TYPES:
        return None
    cfg = _cfg(source)
    password = _dec(source.password_encrypted)

    if wren == "POSTGRES":
        if source.url:
            return {"connectionUrl": source.url}
        user = source.username or ""
        host = source.host or "localhost"
        port = source.port or 5432
        database = source.database or ""
        encoded = quote_plus(password or "")
        url = f"postgresql://{user}:{encoded}@{host}:{port}/{database}"
        if cfg.get("ssl"):
            url += "?sslmode=require"
        return {"connectionUrl": url}

    if wren == "MYSQL":
        return {
            "host": source.host,
            "port": _ibis_port(source.port, 3306),
            "database": source.database,
            "user": source.username,
            "password": password,
            "sslMode": "ENABLED" if cfg.get("ssl") else "DISABLED",
        }

    if wren == "MSSQL":
        info: dict[str, Any] = {
            "host": source.host,
            "port": _ibis_port(source.port, 1433),
            "database": source.database,
            "user": source.username,
            "password": password,
        }
        if cfg.get("trustServerCertificate"):
            info["kwargs"] = {"trustServerCertificate": "YES"}
        return info

    if wren == "ORACLE":
        explicit_dsn = (cfg.get("dsn") or "").strip() or None
        if explicit_dsn:
            return {
                k: v
                for k, v in {
                    "user": (source.username or "").strip().upper() or None,
                    "password": password,
                    "dsn": explicit_dsn,
                }.items()
                if v not in (None, "")
            }
        return {
            k: v
            for k, v in {
                "host": source.host,
                "port": _ibis_port(source.port, 1521),
                "database": source.database,
                "user": (source.username or "").strip().upper() or None,
                "password": password,
            }.items()
            if v not in (None, "")
        }

    if wren == "CLICK_HOUSE":
        return {
            "host": source.host,
            "port": _ibis_port(source.port, 8123),
            "database": source.database,
            "user": source.username,
            "password": password,
            "ssl": bool(cfg.get("ssl")),
        }

    if wren == "TRINO":
        catalog = cfg.get("catalog") or source.database
        schema = source.db_schema or cfg.get("schema")
        if not catalog or not schema:
            return None
        host = (source.host or "").strip()
        if host and not host.startswith(("http://", "https://")):
            host = f"{'https' if cfg.get('ssl') else 'http'}://{host}"
        return {
            "host": host,
            "port": _ibis_port(source.port, 8080),
            "catalog": str(catalog).strip(),
            "schema": str(schema).strip(),
            "user": source.username or cfg.get("username"),
            "password": password,
        }

    if wren == "SNOWFLAKE":
        private_key = cfg.get("privateKey") or cfg.get("private_key") or _dec(source.private_key_encrypted)
        info = {
            "account": cfg.get("account") or source.host,
            "user": source.username or cfg.get("user"),
            "database": source.database or cfg.get("database"),
            "schema": source.db_schema or cfg.get("schema"),
            "warehouse": cfg.get("warehouse") or None,
        }
        if private_key:
            info["private_key"] = private_key
        elif password:
            info["password"] = password
        return {k: v for k, v in info.items() if v not in (None, "")}

    if wren == "BIG_QUERY":
        import base64
        import json

        creds = cfg.get("credentials") or cfg.get("service_account_json")
        if creds is None:
            return None
        if isinstance(creds, str):
            creds_b64 = base64.b64encode(creds.encode()).decode()
        else:
            creds_b64 = base64.b64encode(json.dumps(creds).encode()).decode()
        return {
            "project_id": cfg.get("projectId") or cfg.get("project_id"),
            "dataset_id": cfg.get("datasetId") or cfg.get("dataset_id") or source.database,
            "credentials": creds_b64,
        }

    if wren == "ATHENA":
        base = {
            "region_name": cfg.get("awsRegion") or cfg.get("region_name") or cfg.get("region"),
            "s3_staging_dir": cfg.get("s3StagingDir") or cfg.get("s3_staging_dir"),
            "schema_name": source.db_schema or cfg.get("schema"),
        }
        return {
            **base,
            "aws_access_key_id": cfg.get("awsAccessKey")
            or cfg.get("aws_access_key_id")
            or source.username,
            "aws_secret_access_key": cfg.get("awsSecretKey")
            or cfg.get("aws_secret_access_key")
            or password,
        }

    if wren == "REDSHIFT":
        return {
            "redshift_type": "redshift",
            "host": source.host,
            "port": _ibis_port(source.port, 5439),
            "database": source.database,
            "user": source.username or cfg.get("user"),
            "password": password,
        }

    if wren == "DATABRICKS":
        hostname = cfg.get("serverHostname") or cfg.get("server_hostname") or source.host
        http_path = cfg.get("httpPath") or cfg.get("http_path")
        access_token = (
            cfg.get("accessToken")
            or cfg.get("token")
            or cfg.get("access_token")
            or _dec(source.token_encrypted)
        )
        if not access_token:
            return None
        return {
            "databricks_type": "token",
            "serverHostname": hostname,
            "httpPath": http_path,
            "accessToken": access_token,
        }

    return None
