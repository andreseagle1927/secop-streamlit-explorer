#!/usr/bin/env python3

import os
from typing import Any

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


def _escape(value: str) -> str:
    return value.replace("'", "''")


def build_where(
    departamento: str | None = None,
    ciudad: str | None = None,
    estado_contrato: str | None = None,
    keyword: str | None = None,
) -> str | None:
    conditions: list[str] = []

    if departamento and departamento != "Todos":
        conditions.append(f"departamento = '{_escape(departamento)}'")
    if ciudad and ciudad != "Todos":
        conditions.append(f"ciudad = '{_escape(ciudad)}'")
    if estado_contrato and estado_contrato != "Todos":
        conditions.append(f"estado_contrato = '{_escape(estado_contrato)}'")

    if keyword:
        safe_kw = _escape(keyword.strip().lower())
        if safe_kw:
            conditions.append(
                "("
                f"lower(proveedor_adjudicado) like '%{safe_kw}%' OR "
                f"lower(nombre_entidad) like '%{safe_kw}%' OR "
                f"lower(descripcion_del_proceso) like '%{safe_kw}%'"
                ")"
            )

    if not conditions:
        return None
    return " AND ".join(conditions)


def _execute_get(**kwargs: Any) -> list[dict[str, Any]]:
    client = build_client()
    try:
        return client.get(DATASET_ID, **kwargs)
    except HTTPError as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        if code == 403:
            fallback = Socrata(DOMAIN, None, timeout=30)
            return fallback.get(DATASET_ID, **kwargs)
        raise


def fetch_distinct(column: str, limit: int = 2000) -> list[str]:
    rows = _execute_get(select=f"distinct {column}", order=f"{column} ASC", limit=limit)
    values = [r.get(column, "") for r in rows]
    return [v for v in values if isinstance(v, str) and v.strip()]


def fetch_count(where: str | None = None) -> int:
    params: dict[str, Any] = {"select": "count(*) as total", "limit": 1}
    if where:
        params["where"] = where

    rows = _execute_get(**params)
    if not rows:
        return 0
    return int(rows[0].get("total", 0))


def fetch_rows(
    limit: int = 200,
    offset: int = 0,
    order: str = "fecha_de_firma DESC",
    where: str | None = None,
) -> pd.DataFrame:
    params: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "order": order,
    }
    if where:
        params["where"] = where

    rows = _execute_get(**params)
    return pd.DataFrame.from_records(rows)


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    normalized = df.copy()

    if "valor_del_contrato" in normalized.columns:
        normalized["valor_del_contrato_num"] = pd.to_numeric(
            normalized["valor_del_contrato"], errors="coerce"
        )

    for col in ("fecha_de_firma", "fecha_de_inicio_del_contrato", "fecha_de_fin_del_contrato"):
        if col in normalized.columns:
            normalized[col] = pd.to_datetime(normalized[col], errors="coerce")

    return normalized
