import streamlit as st
import requests
import json
import importlib.util
from pathlib import Path

from app.chat_response import generate_chat_response
from app.config import AP_INVOICE_API_URL, PURCHASE_ORDER_API_URL, PURCHASE_RETURN_API_URL

# --- Configuration ---
st.set_page_config(
    page_title="SAP Purchase Team Orchestrator",
    page_icon="🤖",
    layout="centered",
)

st.title("🤖 SAP Purchase Team Orchestrator")
st.markdown("This interface acts as the **Supervisor Agent**. It routes your natural language requests to the correct sub-agent (Purchase Order, AP Invoice, or Purchase Return).")

# --- Service URLs ---
with st.sidebar:
    st.header("⚙️ Microservice Endpoints")
    po_url = st.text_input("Purchase Order API", value=PURCHASE_ORDER_API_URL)
    ap_url = st.text_input("AP Invoice API", value=AP_INVOICE_API_URL)
    pr_url = st.text_input("Purchase Return API", value=PURCHASE_RETURN_API_URL)
    
    st.header("🔐 Authentication")
    token = st.text_input("JWT Token", type="password", help="Enter a valid JWT token for the backend services")

# --- Session State ---
if "history" not in st.session_state:
    st.session_state.history = []

# --- Helper to load Supervisor Agent ---
@st.cache_resource
def load_supervisor():
    # Load supervisor directly to avoid namespace conflicts with 'app' modules
    current_dir = Path(__file__).parent
    supervisor_path = current_dir / "app" / "agents" / "supervisor_agent.py"
    
    if not supervisor_path.exists():
        st.error(f"Supervisor agent not found at {supervisor_path}")
        return None
        
    spec = importlib.util.spec_from_file_location("purchase_team_supervisor", supervisor_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

supervisor_agent = load_supervisor()

# --- Chat Interface ---
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "decision" in msg or "api_response" in msg:
            with st.expander("Technical details"):
                if "decision" in msg:
                    st.json(msg["decision"])
                if "api_response" in msg:
                    st.json(msg["api_response"])

prompt = st.chat_input("Enter your request (e.g., 'Update purchase return 12345 with comments...')")

if prompt:
    # 1. Show user prompt
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not supervisor_agent:
            st.error("Failed to load Supervisor Agent.")
            st.stop()
            
        # 2. Get routing decision
        with st.spinner("Routing request..."):
            try:
                # The execute method returns a Pydantic model PurchaseTeamRoutingResponse
                routing_response = supervisor_agent.execute(prompt)
                response_data = routing_response.model_dump()["data"]
                decision_data = response_data.get("fetchAgent")
                if not decision_data:
                    st.json(response_data)
                    raise RuntimeError("Supervisor did not return a fetchAgent routing decision.")
                
                with st.expander("Supervisor decision", expanded=False):
                    st.success(f"Routed to: **{decision_data['subagent']}**")
                    st.json(decision_data)
                
            except Exception as e:
                st.error(f"Routing failed: {e}")
                st.stop()
                
        # 3. Execute against backend
        st.caption(f"Executing on {decision_data['documentType'].replace('_', ' ')} backend...")
        
        url_map = {
            "purchase_order": po_url,
            "ap_invoice": ap_url,
            "purchase_return": pr_url
        }
        
        target_url = url_map.get(decision_data["documentType"])
        
        if not target_url:
            st.error(f"No mapped URL for {decision_data['documentType']}")
        elif not token:
            st.warning("⚠️ No JWT Token provided. The backend request will likely fail with 401 Unauthorized.")
            
        with st.spinner(f"Calling {target_url}..."):
            try:
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    
                response = requests.post(
                    target_url,
                    json={"prompt": prompt},
                    headers=headers,
                    timeout=30
                )
                
                api_response = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"detail": response.text}
                
                chat_answer = generate_chat_response(
                    prompt=prompt,
                    routing_decision=decision_data,
                    api_response=api_response,
                    status_code=response.status_code,
                )
                st.markdown(chat_answer)

                with st.expander("Backend response", expanded=False):
                    if response.status_code in (200, 201):
                        st.success("Execution successful")
                    else:
                        st.error(f"Execution failed (HTTP {response.status_code})")
                    st.json(api_response)
                    
                st.session_state.history.append({
                    "role": "assistant", 
                    "content": chat_answer,
                    "decision": decision_data,
                    "api_response": api_response
                })
                
            except requests.exceptions.ConnectionError:
                api_response = {"detail": f"Could not connect to {target_url}. Is the FastAPI server running?"}
                chat_answer = generate_chat_response(prompt, decision_data, api_response, None)
                st.markdown(chat_answer)
                st.session_state.history.append({
                    "role": "assistant",
                    "content": chat_answer,
                    "decision": decision_data,
                    "api_response": api_response,
                })
            except Exception as e:
                api_response = {"detail": str(e)}
                chat_answer = generate_chat_response(prompt, decision_data, api_response, None)
                st.markdown(chat_answer)
