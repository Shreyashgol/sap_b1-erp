import json
from typing import Any

import requests
import streamlit as st

from app.agents.supervisor.supervisor_agent import execute as route_prompt
from app.chat_response import generate_chat_response


DEFAULT_API_URL = "http://127.0.0.1:8000"

ROUTE_ENDPOINTS = {
    "purchase_order": "/purchase-orders/parse-and-execute",
    "ap_invoice": "/ap-invoices/parse-and-execute",
    "purchase_return": "/purchase-returns/parse-and-execute",
}


st.set_page_config(
    page_title="SAP Purchase Supervisor",
    page_icon="SAP",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; max-width: 920px; }
div[data-testid="stSidebar"] { border-right: 1px solid #d7dee8; }
.status-pill {
    display:inline-block;
    padding:4px 10px;
    border:1px solid #b7c4d6;
    border-radius:999px;
    font-size:12px;
    color:#334155;
    background:#f8fafc;
}
.technical-box {
    border:1px solid #d7dee8;
    border-radius:8px;
    padding:12px;
    background:#ffffff;
}
</style>
""",
    unsafe_allow_html=True,
)


def call_backend(api_url: str,endpoint: str,prompt: str,token: str | None) -> tuple[int | None, dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

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


for key, default in {
    "token": None,
    "history": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


with st.sidebar:
    st.title("SAP Purchase")
    st.caption("One Supervisor Agent routes every request.")

    api_url = st.text_input("FastAPI URL", value=DEFAULT_API_URL)

    st.divider()
    st.subheader("Login")
    username = st.text_input("Username", value="user1")
    password = st.text_input("Password", type="password", value="pass123456")
    if st.button("Login", use_container_width=True):
        try:
            response = requests.post(
                f"{api_url.rstrip('/')}/login",
                params={"username": username, "password": password},
                timeout=15,
            )
            if response.status_code == 200:
                st.session_state.token = response.json()["access_token"]
                st.success("Authenticated.")
            else:
                st.session_state.token = None
                st.error(response.text)
        except Exception as exc:
            st.session_state.token = None
            st.error(f"Login failed: {exc}")

    if st.session_state.token:
        st.markdown('<span class="status-pill">Token active</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill">Not authenticated</span>', unsafe_allow_html=True)

    st.divider()
    show_json = st.toggle("Show technical details", value=False)
    if st.button("Clear chat", use_container_width=True):
        st.session_state.history = []
        st.rerun()


st.title("SAP B1 Purchase Supervisor Agent")
st.caption("Ask naturally. The supervisor routes to purchase order, AP invoice, or purchase return agents.")

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and show_json:
            with st.expander("Supervisor and backend details"):
                routing = message.get("routing")
                api_response = message.get("api_response")
                if routing:
                    if api_response and isinstance(api_response, dict) and "data" in api_response and "sql" in api_response["data"]:
                        st.markdown("#### 1. Agent Flow")
                        doc_type = routing.get("documentType", "unknown").replace("_", " ").title()
                        action = routing.get("action", "unknown").title()
                        st.info(f"**Supervisor Agent** ➡️ **{action} {doc_type} Sub-Agent**")
                        st.json(routing)
                        st.markdown("#### 2. SQL Generation")
                        sql_query = api_response.get("data", {}).get("sql", "N/A")
                        st.code(sql_query, language="sql")
                        st.markdown("#### 3. JSON Response")
                        
                        # Show relevant data part based on action
                        if routing.get("action") == "fetch":
                            st.json(api_response.get("data", {}).get("results", api_response.get("data", {}).get("rows", [])))
                        else:
                            st.json(api_response.get("data", {}).get("sapResponse", api_response))
                    else:
                        st.json(routing)
                        if api_response:
                            st.json(api_response)

prompt = st.chat_input("Example: Show me the latest 5 purchase orders for vendor V001")

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        if not st.session_state.token:
            message = "Please login from the sidebar before I execute the request."
            st.warning(message)
            st.session_state.history.append({"role": "assistant", "content": message})
            st.stop()

        with st.spinner("Supervisor is routing the request..."):
            try:
                routing_response = route_prompt(prompt)
                response_data = routing_response.model_dump()["data"]
                routing_decision = response_data.get("fetchAgent")
                if not routing_decision:
                    raise RuntimeError("Supervisor did not return a routing decision.")
                 
                target_endpoint = ROUTE_ENDPOINTS.get(routing_decision["documentType"])
                if not target_endpoint:
                    raise RuntimeError(f"No backend endpoint mapped for {routing_decision['documentType']}.")

                status_code, api_response = call_backend(
                    api_url=api_url,
                    endpoint=target_endpoint,
                    prompt=prompt,
                    token=st.session_state.token,
                )
                assistant_reply = generate_chat_response(
                    prompt=prompt,
                    routing_decision=routing_decision,
                    api_response=api_response,
                    status_code=status_code,
                )

                st.markdown(assistant_reply)
                if show_json:
                    with st.expander("Supervisor and backend details", expanded=False):
                        if api_response and isinstance(api_response, dict) and "data" in api_response and "sql" in api_response["data"]:
                            st.markdown("#### 1. Agent Flow")
                            doc_type = routing_decision.get("documentType", "unknown").replace("_", " ").title()
                            action = routing_decision.get("action", "unknown").title()
                            st.info(f"**Supervisor Agent** ➡️ **{action} {doc_type} Sub-Agent**")
                            st.json(routing_decision)
                            st.markdown("#### 2. SQL Generation")
                            sql_query = api_response.get("data", {}).get("sql", "N/A")
                            st.code(sql_query, language="sql")
                            st.markdown("#### 3. JSON Response")
                            
                            # Show relevant data part based on action
                            if routing_decision.get("action") == "fetch":
                                st.json(api_response.get("data", {}).get("results", api_response.get("data", {}).get("rows", [])))
                            else:
                                st.json(api_response.get("data", {}).get("sapResponse", api_response))
                        else:
                            st.json(routing_decision)
                            st.code(json.dumps(api_response, indent=2, default=str), language="json")

                st.session_state.history.append(
                    {
                        "role": "assistant",
                        "content": assistant_reply,
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
