import importlib.util
from pathlib import Path

from app.agents.supervisor.fetch_agent import decide
from app.schema.response import PurchaseTeamRoutingResponse


def _load_supervisor_graph():
    graph_path = Path(__file__).with_name("supervisor_graph.py")
    spec = importlib.util.spec_from_file_location("supervisor_graph_module", graph_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load supervisor graph from {graph_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.supervisor_app


def execute(prompt: str) -> PurchaseTeamRoutingResponse:
    app = _load_supervisor_graph()
    
    # Run the state graph
    result_state = app.invoke({"prompt": prompt})
    
    if result_state.get("error"):
        decision = decide(prompt)
        return PurchaseTeamRoutingResponse(
            status="routed",
            message=f"Supervisor used local fallback after graph error: {result_state['error']}",
            data={
                "supervisor": {
                    "decision": f"Fallback routing to {decision['subagent']}",
                    "agent": "local_keyword_router",
                    "documentType": decision["documentType"],
                    "action": decision["action"],
                    "reason": result_state["error"],
                },
                "fetchAgent": decision,
            },
        )

    decision = result_state.get("routing_decision") or decide(prompt)
    
    return PurchaseTeamRoutingResponse(
        status="routed",
        message=f"Supervisor routed request to {decision['subagent']}.",
        data={
            "supervisor": {
                "decision": f"LangGraph routing to {decision['subagent']}",
                "agent": "supervisor_graph",
                "documentType": result_state.get("document_type"),
                "action": result_state.get("action"),
                "reason": result_state.get("reason"),
            },
            "fetchAgent": decision,
        },
    )
