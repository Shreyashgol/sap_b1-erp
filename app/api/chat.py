from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.big_supervisor_agent import execute_prompt
from app.chat_response import generate_chat_response

router = APIRouter()


class ChatRequest(BaseModel):
    prompt: str
    conversation_history: Optional[List[Dict[str, Any]]] = None


class ChatResponse(BaseModel):
    reply: str
    team: str
    routing: Dict[str, Any]
    api_response: Dict[str, Any]
    status_code: int


@router.post("", response_model=ChatResponse)
def execute_chat(request: ChatRequest):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    try:
        graph_state = execute_prompt(prompt, request.conversation_history)
        route_result = graph_state.get("route_result", {})
        team = route_result.get("team", graph_state.get("team", "purchase"))
        routing_decision = graph_state.get("routing_decision", route_result.get("routing_decision", {}))
        api_response_data = graph_state.get("api_response", {})
        status_code = graph_state.get("status_code", 200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agentic workflow failed: {str(exc)}") from exc

    try:
        assistant_reply = generate_chat_response(
            prompt=prompt,
            routing_decision=routing_decision,
            api_response=api_response_data,
            status_code=status_code,
            conversation_history=request.conversation_history,
        )
    except Exception as exc:
        assistant_reply = (
            f"I encountered an error synthesizing the final response: {str(exc)}.\n\n"
            f"Technical Details: {api_response_data.get('detail', str(api_response_data))}"
        )

    return ChatResponse(
        reply=assistant_reply,
        team=team,
        routing=routing_decision,
        api_response=api_response_data,
        status_code=status_code,
    )
