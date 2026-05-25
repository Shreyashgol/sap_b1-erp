from app.operations.claude_client import claude_chat_completion


def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: int = 120,
) -> str:
    return claude_chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
