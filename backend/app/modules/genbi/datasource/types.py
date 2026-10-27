"""Wren 数据源类型，对齐 tiga-case WREN_DATA_SOURCE_TYPES / genbiConnectionTypes。"""

WREN_TYPES: frozenset[str] = frozenset(
    {
        "BIG_QUERY",
        "DUCKDB",
        "POSTGRES",
        "MYSQL",
        "ORACLE",
        "MSSQL",
        "CLICK_HOUSE",
        "TRINO",
        "SNOWFLAKE",
        "ATHENA",
        "REDSHIFT",
        "DATABRICKS",
    }
)
