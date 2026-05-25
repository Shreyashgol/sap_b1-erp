import json
from decimal import Decimal
from typing import Any

import pandas as pd
import requests
import streamlit as st

from app.agents.big_supervisor_agent import route as big_supervisor_route
from app.chat_response import generate_chat_response
from app.config import BIG_SUPERVISOR_CLAUDE_MODEL, SALES_SQL_CLAUDE_MODEL, SALES_TEAM_CLAUDE_MODEL


DEFAULT_API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="SAP ERP Supervisor",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.block-container { padding-top: 1.5rem; max-width: 1200px; }
div[data-testid="stSidebar"] { border-right: 1px solid #d7dee8; }
.status-pill {
    display:inline-block; padding:4px 10px;
    border:1px solid #b7c4d6; border-radius:999px;
    font-size:12px; color:#334155; background:#f8fafc;
}
.team-badge-purchase {
    display:inline-block; padding:3px 10px;
    border-radius:999px; font-size:12px; font-weight:600;
    background:#dbeafe; color:#1d4ed8; border:1px solid #93c5fd;
}
.team-badge-sales {
    display:inline-block; padding:3px 10px;
    border-radius:999px; font-size:12px; font-weight:600;
    background:#dcfce7; color:#15803d; border:1px solid #86efac;
}
</style>
""",
    unsafe_allow_html=True,
)


def call_backend(api_url: str, endpoint: str, prompt: str) -> tuple[int | None, dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        f"{api_url.rstrip('/')}{endpoint}",
        json={"prompt": prompt},
        headers=headers,
        timeout=120,
    )
    body = (
        response.json()
        if response.headers.get("content-type", "").startswith("application/json")
        else {"detail": response.text}
    )
    return response.status_code, body


def wants_chart(prompt: str) -> bool:
    lowered = prompt.lower()
    chart_terms = (
        "chart",
        "graph",
        "plot",
        "visualize",
        "visualise",
        "bar chart",
        "line chart",
        "trend",
        "dashboard",
    )
    return any(term in lowered for term in chart_terms)


def extract_rows(api_response: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(api_response, dict):
        return []
    data = api_response.get("data") or {}
    rows = data.get("results") or data.get("rows") or data.get("value") or []
    return rows if isinstance(rows, list) and all(isinstance(row, dict) for row in rows) else []


def _flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                flattened[f"{key}_{child_key}"] = child_value
        elif not isinstance(value, list):
            flattened[key] = value
    return flattened


def render_requested_chart(prompt: str, api_response: dict[str, Any]):
    rows = extract_rows(api_response)
    if not wants_chart(prompt) or not rows:
        return

    df = pd.DataFrame([_flatten_row(row) for row in rows])
    if df.empty:
        return

    for column in df.columns:
        df[column] = df[column].map(lambda value: float(value) if isinstance(value, Decimal) else value)

    numeric_columns = list(df.select_dtypes(include="number").columns)
    if not numeric_columns:
        st.info("I found rows for this query, but there is no numeric column to chart.")
        st.dataframe(df, use_container_width=True)
        return

    text_columns = list(df.select_dtypes(include=["object", "string"]).columns)
    date_like_columns = [
        column for column in df.columns
        if "date" in column.lower() or "month" in column.lower() or "year" in column.lower()
    ]
    x_column = date_like_columns[0] if date_like_columns else (text_columns[0] if text_columns else df.columns[0])
    y_column = numeric_columns[0]

    st.markdown("#### Chart")
    chart_df = df[[x_column, y_column]].dropna()
    chart_df[x_column] = chart_df[x_column].astype(str)
    chart_df = chart_df.set_index(x_column)

    lowered = prompt.lower()
    if "line" in lowered or "trend" in lowered or "month" in lowered or "date" in lowered:
        st.line_chart(chart_df, use_container_width=True)
    elif "area" in lowered:
        st.area_chart(chart_df, use_container_width=True)
    else:
        st.bar_chart(chart_df, use_container_width=True)

    with st.expander("View chart data"):
        st.dataframe(df, use_container_width=True)


# ── Session state init ────────────────────────────────────────────────────────
for key, default in {"history": []}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("SAP ERP Supervisor")
    st.caption("Big Supervisor routes each request to Purchase Team or Sales Team sub-agents.")

    api_url = st.text_input("FastAPI URL", value=DEFAULT_API_URL)

    st.divider()
    st.divider()

    st.divider()
    show_json = st.toggle("Show technical details", value=False)
    if st.button("Clear chat", use_container_width=True):
        st.session_state.history = []
        st.rerun()

    st.divider()
    st.markdown("**Teams Available**")
    st.markdown("🔵 **Purchase Team** — PO, AP Invoice, Purchase Return")
    st.markdown("🟢 **Sales Team** — SO, AR Invoice, Sales Return")
    st.caption(
        f"Claude models: supervisor `{BIG_SUPERVISOR_CLAUDE_MODEL}`, "
        f"sales parser `{SALES_TEAM_CLAUDE_MODEL}`, sales SQL `{SALES_SQL_CLAUDE_MODEL}`"
    )


# ── Main chat area ────────────────────────────────────────────────────────────
st.title("🏢 SAP B1 ERP Supervisor Agent")
st.caption(
    "Ask anything in plain English. The Big Supervisor calls either the **Purchase Team** "
    "or the **Sales Team**, then routes to the correct sub-agent."
)

# Render chat history
for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_requested_chart(message.get("prompt", ""), message.get("api_response") or {})
        if message["role"] == "assistant" and show_json:
            _team = message.get("team", "purchase")
            _routing = message.get("routing")
            _api_response = message.get("api_response")
            with st.expander("🔍 Big Supervisor & backend details"):
                if _routing:
                    st.markdown("#### 1. Routing Flow")
                    _team_label = message.get("team_label", _team.title() + " Team")
                    _badge_cls = "team-badge-sales" if _team == "sales" else "team-badge-purchase"
                    _doc_type = _routing.get("documentType", "unknown").replace("_", " ").title()
                    _action = _routing.get("action", "fetch").title()
                    _subagent = _routing.get("subagent", "")
                    st.markdown(
                        f'**Big Supervisor** -> <span class="{_badge_cls}">{_team_label}</span> -> **{_action} {_doc_type} Sub-Agent**',
                        unsafe_allow_html=True,
                    )
                    st.json(_routing)

                if _api_response and isinstance(_api_response, dict) and "data" in _api_response:
                    _data = _api_response["data"]
                    if "agent" in _data:
                        st.markdown("#### 2. Sub-Agent Execution")
                        st.json(
                            {
                                "agent": _data.get("agent"),
                                "strategy": _data.get("strategy"),
                                "documentType": _data.get("documentType"),
                                "workflow": _data.get("workflow"),
                            }
                        )
                    if "sql" in _data:
                        st.markdown("#### 3. HANA SQL Generated")
                        st.code(_data["sql"], language="sql")
                    if "filters" in _data:
                        st.markdown("#### 4. RAG / Filter Metadata")
                        st.json(_data["filters"])
                    st.markdown("#### 5. JSON Response")
                    _results = _data.get("results", _data.get("rows", _data.get("sapResponse", _api_response)))
                    st.json(_results)


# ── Chat input ────────────────────────────────────────────────────────────────
prompt = st.chat_input(
    "Example: Show top 5 sales orders | Show overdue purchase orders"
)

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # No login required

        with st.spinner("Big Supervisor is routing the request..."):
            try:
                # ── Step 1: Big Supervisor decides team + endpoint ────────────
                big_result = big_supervisor_route(prompt)
                team = big_result["team"]
                team_label = big_result["team_label"]
                endpoint = big_result["endpoint"]
                routing_decision = big_result["routing_decision"]

                # ── Step 2: Call the right backend endpoint ───────────────────
                status_code, api_response = call_backend(
                    api_url=api_url,
                    endpoint=endpoint,
                    prompt=prompt
                )

                # ── Step 3: Generate chat reply ───────────────────────────────
                assistant_reply = generate_chat_response(
                    prompt=prompt,
                    routing_decision=routing_decision,
                    api_response=api_response,
                    status_code=status_code,
                )

                st.markdown(assistant_reply)
                render_requested_chart(prompt, api_response)

                # ── Step 4: Technical details expander ───────────────────────
                if show_json:
                    _badge_cls = "team-badge-sales" if team == "sales" else "team-badge-purchase"
                    with st.expander("🔍 Big Supervisor & backend details", expanded=False):
                        st.markdown("#### 1. Routing Flow")
                        doc_type_label = routing_decision.get("documentType", "unknown").replace("_", " ").title()
                        action_label = routing_decision.get("action", "fetch").title()
                        st.markdown(
                            f'**Big Supervisor** -> <span class="{_badge_cls}">{team_label}</span> -> **{action_label} {doc_type_label} Sub-Agent**',
                            unsafe_allow_html=True,
                        )
                        st.json(routing_decision)

                        if api_response and isinstance(api_response, dict) and "data" in api_response:
                            data = api_response["data"]
                            if "agent" in data:
                                st.markdown("#### 2. Sub-Agent Execution")
                                st.json(
                                    {
                                        "agent": data.get("agent"),
                                        "strategy": data.get("strategy"),
                                        "documentType": data.get("documentType"),
                                        "workflow": data.get("workflow"),
                                    }
                                )
                            if "sql" in data:
                                st.markdown("#### 3. HANA SQL Generated")
                                st.code(data["sql"], language="sql")
                            if "filters" in data:
                                st.markdown("#### 4. RAG / Filter Metadata")
                                st.json(data["filters"])
                            st.markdown("#### 5. JSON Response")
                            results = data.get(
                                "results",
                                data.get("rows", data.get("sapResponse", api_response)),
                            )
                            st.json(results)
                        else:
                            st.code(json.dumps(api_response, indent=2, default=str), language="json")

                # ── Step 5: Save to history ───────────────────────────────────
                st.session_state.history.append(
                    {
                        "role": "assistant",
                        "content": assistant_reply,
                        "prompt": prompt,
                        "team": team,
                        "team_label": team_label,
                        "routing": routing_decision,
                        "api_response": api_response,
                    }
                )

            except requests.exceptions.ConnectionError:
                message = f"Could not connect to `{api_url}`. Start the FastAPI backend first."
                st.error(message)
                st.session_state.history.append({"role": "assistant", "content": message})
            except Exception as exc:
                message = f"Routing or execution failed: {exc}"
                st.error(message)
                st.session_state.history.append({"role": "assistant", "content": message})
