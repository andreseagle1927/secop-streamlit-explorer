#!/usr/bin/env python3

import argparse
import os

import pandas as pd
from requests.exceptions import HTTPError
from sodapy import Socrata


DATASET_ID = "jbjy-vk9h"
DOMAIN = "www.datos.gov.co"


def build_client() -> Socrata:
    app_token = os.getenv("APP_TOKEN")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if app_token and username and password:
        return Socrata(
            DOMAIN,
            app_token,
            username=username,
            password=password,
            timeout=30,
        )

    return Socrata(DOMAIN, None, timeout=30)


def fetch_rows(limit: int) -> list[dict]:
    client = build_client()
    try:
        return client.get(DATASET_ID, limit=limit)
    except HTTPError as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        if code == 403:
            fallback = Socrata(DOMAIN, None, timeout=30)
            return fallback.get(DATASET_ID, limit=limit)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch SECOP data from datos.gov.co")
    parser.add_argument("--limit", type=int, default=2000, help="Rows to fetch")
    parser.add_argument("--out", default="secop_jbjy-vk9h.csv", help="Output CSV path")
    args = parser.parse_args()

    rows = fetch_rows(args.limit)
    df = pd.DataFrame.from_records(rows)
    df.to_csv(args.out, index=False)

    print(f"rows={len(df)}")
    print(f"columns={len(df.columns)}")
    print(f"saved={args.out}")


if __name__ == "__main__":
    main()
