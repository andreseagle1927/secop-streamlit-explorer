#!/usr/bin/env python3

import math
from io import StringIO

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from secop_client import build_where, fetch_count, fetch_distinct, fetch_rows, normalize_dataframe


load_dotenv()

st.set_page_config(page_title="SECOP Explorer", page_icon="📊", layout="wide")
st.link_button("Home", "http://135.181.182.60:8500/", use_container_width=False)
st.image("logoProtelec.png", width=180)


@st.cache_data(ttl=300)
def cached_distinct(column: str) -> list[str]:
    return fetch_distinct(column)


@st.cache_data(ttl=120)
def cached_count(where: str | None) -> int:
    return fetch_count(where)


@st.cache_data(ttl=120)
def cached_rows(where: str | None, limit: int, offset: int, order: str) -> pd.DataFrame:
    raw_df = fetch_rows(limit=limit, offset=offset, order=order, where=where)
    return normalize_dataframe(raw_df)


def build_top7_pie_source(series: pd.Series) -> pd.DataFrame:
    normalized = series.fillna("(sin dato)").astype(str).str.strip()
    normalized = normalized.replace("", "(sin dato)")
    counts = normalized.value_counts()

    top = counts.head(7)
    other_count = int(counts.iloc[7:].sum())

    labels = top.index.tolist()
    values = top.astype(int).tolist()
    if other_count > 0:
        labels.append("Otros")
        values.append(other_count)

    return pd.DataFrame({"categoria": labels, "cantidad": values})


st.title("SECOP explorador")
st.caption("Dataset: jbjy-vk9h · Source: www.datos.gov.co")

with st.sidebar:
    st.header("Filters")

    departamentos = ["Todos"] + cached_distinct("departamento")
    ciudades = ["Todos"] + cached_distinct("ciudad")
    estados = ["Todos"] + cached_distinct("estado_contrato")

    departamento = st.selectbox("Departamento", departamentos, index=0)
    ciudad = st.selectbox("Ciudad", ciudades, index=0)
    estado = st.selectbox("Estado contrato", estados, index=0)
    keyword = st.text_input("Keyword", placeholder="proveedor, entidad, descripcion")

    st.header("Query")
    page_size = st.selectbox("Rows per page", [50, 100, 200, 500, 1000], index=2)
    page = st.number_input("Page", min_value=1, value=1, step=1)

    order_map = {
        "Fecha firma (newest)": "fecha_de_firma DESC",
        "Fecha firma (oldest)": "fecha_de_firma ASC",
        "Valor contrato (high)": "valor_del_contrato DESC",
        "Valor contrato (low)": "valor_del_contrato ASC",
    }
    order_label = st.selectbox("Order", list(order_map.keys()), index=0)
    order = order_map[order_label]

    st.header("Columns")
    show_all_columns = st.checkbox("Show all columns", value=False)

    if st.button("Refresh cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

where = build_where(
    departamento=departamento,
    ciudad=ciudad,
    estado_contrato=estado,
    keyword=keyword,
)

offset = (int(page) - 1) * int(page_size)

try:
    total_rows = cached_count(where)
    df = cached_rows(where, int(page_size), int(offset), order)
except Exception as exc:
    st.error(f"Failed to load data from API: {exc}")
    st.stop()

total_pages = max(1, math.ceil(total_rows / page_size))

k1, k2, k3 = st.columns(3)
k1.metric("Rows matching filters", f"{total_rows:,}")
k2.metric("Current page", f"{len(df):,}")

total_value = 0.0
if "valor_del_contrato_num" in df.columns:
    total_value = float(df["valor_del_contrato_num"].fillna(0).sum())
k3.metric("Current page contract sum", f"${total_value:,.0f}")

st.caption(f"Page {page} of {total_pages}")

preferred_cols = [
    "fecha_de_firma",
    "nombre_entidad",
    "departamento",
    "ciudad",
    "estado_contrato",
    "proveedor_adjudicado",
    "valor_del_contrato",
]
displayable_cols = [c for c in df.columns if c != "valor_del_contrato_num"]
default_cols = [c for c in preferred_cols if c in displayable_cols]
if not default_cols:
    default_cols = displayable_cols

if show_all_columns:
    selected_cols = displayable_cols
else:
    selected_cols = st.multiselect(
        "Choose columns",
        options=displayable_cols,
        default=default_cols,
    )
    if not selected_cols:
        selected_cols = default_cols

st.dataframe(df[selected_cols], use_container_width=True, height=480)

if "nombre_entidad" in df.columns and not df.empty:
    st.subheader("Top entidades (current page)")
    top_entities = df["nombre_entidad"].fillna("(sin dato)").value_counts().head(10)
    st.bar_chart(top_entities)

pie_fields = [
    "departamento",
    "ciudad",
    "estado_contrato",
    "proveedor_adjudicado",
    "orden",
    "sector",
    "rama",
    "tipo_de_contrato",
    "modalidad_de_contratacion",
    "justificacion_modalidad_de",
]

available_pie_fields = [field for field in pie_fields if field in df.columns]

st.subheader("Distribucion por categoria (current page)")
if df.empty:
    st.info("No hay filas en la pagina actual para graficar.")
elif not available_pie_fields:
    st.info("No se encontraron columnas objetivo para graficos de pastel en esta pagina.")
else:
    pie_colors = [
        "#0074D9",
        "#0B294A",
        "#7FDBFF",
        "#005EA6",
        "#2D8CFF",
        "#4BA3F0",
        "#8EC8FF",
        "#C8D4E3",
    ]
    for i in range(0, len(available_pie_fields), 2):
        cols = st.columns(2)
        for col, field in zip(cols, available_pie_fields[i : i + 2]):
            with col:
                pie_df = build_top7_pie_source(df[field])
                fig = px.pie(
                    pie_df,
                    names="categoria",
                    values="cantidad",
                    title=f"{field} (top 7 + otros)",
                    color_discrete_sequence=pie_colors,
                )
                fig.update_traces(textposition="inside", textinfo="percent+label", hovertemplate="%{label}<br>Cantidad: %{value}<br>Porcentaje: %{percent}<extra></extra>")
                fig.update_layout(margin=dict(l=10, r=10, t=45, b=10), height=420)
                st.plotly_chart(fig, use_container_width=True)

export_df = df[selected_cols].copy()

csv_buffer = StringIO()
export_df.to_csv(csv_buffer, index=False)

json_payload = export_df.to_json(orient="records", date_format="iso", force_ascii=False)
xml_payload = export_df.to_xml(index=False, root_name="rows", row_name="row")

st.subheader("Export")
e1, e2, e3 = st.columns(3)

e1.download_button(
    "Export CSV",
    data=csv_buffer.getvalue(),
    file_name="secop_filtered_page.csv",
    mime="text/csv",
    use_container_width=True,
)
e2.download_button(
    "Export JSON",
    data=json_payload,
    file_name="secop_filtered_page.json",
    mime="application/json",
    use_container_width=True,
)
e3.download_button(
    "Export XML",
    data=xml_payload,
    file_name="secop_filtered_page.xml",
    mime="application/xml",
    use_container_width=True,
)

with st.expander("Active SoQL where"):
    st.code(where if where else "(no filters)")
