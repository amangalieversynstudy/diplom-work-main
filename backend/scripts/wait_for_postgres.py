#!/usr/bin/env python3
"""Wait for Postgres to become available using psycopg2.

This script attempts to open a connection repeatedly for up to 60 seconds.
It exits with non-zero status if the DB does not become available.
"""
import os
import time

import psycopg2


def main():
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
