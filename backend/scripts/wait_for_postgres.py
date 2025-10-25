#!/usr/bin/env python3
"""Utilities to wait until PostgreSQL is accepting connections.

This script is used by CI and container entrypoints to wait for the
Postgres service to become available before running migrations or tests.
"""
import os
import time

import psycopg2


def main():
    """Attempt to connect to Postgres repeatedly, returning 0 on success.

    Returns non-zero exit code if Postgres is not available within timeout.
    """
    for i in range(60):
        try:
            conn = psycopg2.connect(
                dbname=os.environ.get("POSTGRES_DB", "rpgdb"),
                user=os.environ.get("POSTGRES_USER", "rpguser"),
                password=os.environ.get("POSTGRES_PASSWORD", "rpgpass"),
                host=os.environ.get("POSTGRES_HOST", "postgres"),
                port=os.environ.get("POSTGRES_PORT", "5432"),
            )
            conn.close()
            print("postgres ready")
            return 0
        except Exception as e:
            print("waiting for postgres...", e)
            time.sleep(1)
    print("postgres did not become ready")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
