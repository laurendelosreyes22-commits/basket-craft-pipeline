# tests/test_load_snowflake.py
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from pipeline.load_snowflake import load_snowflake


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("RDS_USER", "user")
    monkeypatch.setenv("RDS_PASSWORD", "pass")
    monkeypatch.setenv("RDS_HOST", "localhost")
    monkeypatch.setenv("RDS_PORT", "5432")
    monkeypatch.setenv("RDS_DATABASE", "db")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("SNOWFLAKE_USER", "sfuser")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "sfpass")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "wh")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "BASKET_CRAFT")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "RAW")


def _make_mocks(tables, row_counts):
    """Return (sf_conn, engine, inspector_mock, cursor_mock) wired together."""
    # Snowflake cursor — returns COUNT(*) values in order
    cursor = MagicMock()
    cursor.fetchone.side_effect = [(n,) for n in row_counts]

    # Snowflake connection — context manager
    sf_conn = MagicMock()
    sf_conn.__enter__ = MagicMock(return_value=sf_conn)
    sf_conn.__exit__ = MagicMock(return_value=False)
    sf_conn.cursor.return_value = cursor

    # RDS connection — context manager
    rds_conn = MagicMock()
    rds_conn.__enter__ = MagicMock(return_value=rds_conn)
    rds_conn.__exit__ = MagicMock(return_value=False)

    # SQLAlchemy engine
    engine = MagicMock()
    engine.connect.return_value = rds_conn

    # Inspector
    inspector = MagicMock()
    inspector.get_table_names.return_value = tables

    return sf_conn, engine, inspector, cursor


def test_columns_are_uppercased(mock_env):
    """DataFrame column names must be uppercase before write_pandas is called."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1, "customer_id": 101}])
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[1])

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 1, "")
        load_snowflake()

    called_df = mock_wp.call_args[0][1]
    assert list(called_df.columns) == ["ORDER_ID", "CUSTOMER_ID"]


def test_table_name_is_uppercase(mock_env):
    """table_name passed to write_pandas must be uppercase."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1}])
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[1])

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 1, "")
        load_snowflake()

    assert mock_wp.call_args[1]["table_name"] == "ORDERS"


def test_row_count_mismatch_raises(mock_env):
    """RuntimeError must be raised when Snowflake COUNT(*) does not match len(df)."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1}, {"order_id": 2}])  # 2 rows
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[1])  # Snowflake returns 1

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 2, "")
        with pytest.raises(RuntimeError, match="orders: sent"):
            load_snowflake()


def test_row_count_match_does_not_raise(mock_env):
    """No error when Snowflake COUNT(*) matches the number of rows sent."""
    tables = ["orders"]
    df = pd.DataFrame([{"order_id": 1}, {"order_id": 2}])  # 2 rows
    sf_conn, engine, inspector, _ = _make_mocks(tables, row_counts=[2])  # Snowflake returns 2

    with (
        patch("pipeline.load_snowflake.create_engine", return_value=engine),
        patch("pipeline.load_snowflake.inspect", return_value=inspector),
        patch("pipeline.load_snowflake.snowflake.connector.connect", return_value=sf_conn),
        patch("pipeline.load_snowflake.pd.read_sql", return_value=df),
        patch("pipeline.load_snowflake.write_pandas") as mock_wp,
    ):
        mock_wp.return_value = (True, 1, 2, "")
        load_snowflake()  # must not raise
