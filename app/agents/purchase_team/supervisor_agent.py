from app.agents.purchase_team.fetch_agent import decide
from app.schema.response import PurchaseTeamRoutingResponse


def execute(prompt: str) -> PurchaseTeamRoutingResponse:
    decision = decide(prompt)
    
    return PurchaseTeamRoutingResponse(
        status="routed",
        message=f"Supervisor routed request to {decision['subagent']}.",
        data={
            "supervisor": {
                "decision": f"Routing to {decision['subagent']}",
                "agent": "purchase_team_router",
                "documentType": decision["documentType"],
                "action": decision["action"],
            },
            "fetchAgent": decision,
        },
    )
