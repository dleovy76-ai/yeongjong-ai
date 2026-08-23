from core.config import _with_psycopg_driver


def test_with_psycopg_driver_rewrites_plain_postgresql_scheme():
    assert _with_psycopg_driver("postgresql://user:pw@host:5432/db") == "postgresql+psycopg://user:pw@host:5432/db"


def test_with_psycopg_driver_rewrites_short_postgres_scheme():
    assert _with_psycopg_driver("postgres://user:pw@host:5432/db") == "postgresql+psycopg://user:pw@host:5432/db"


def test_with_psycopg_driver_leaves_already_correct_scheme_alone():
    url = "postgresql+psycopg://user:pw@host:5432/db"
    assert _with_psycopg_driver(url) == url
