from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def main() -> None:
    if not settings.llm_api_key:
        raise SystemExit("HEALTH_AGENT_LLM_API_KEY is required")

    app = create_app()
    client = TestClient(app)

    session_response = client.post("/api/agent/sessions", json={"title": "新对话"})
    print("create_session", session_response.status_code)
    session_response.raise_for_status()
    session_id = session_response.json()["session_id"]

    events: list[str] = []
    with client.stream(
        "POST",
        f"/api/agent/sessions/{session_id}/messages:stream",
        json={"content": "请用一句话说明你能帮我做什么。"},
    ) as response:
        print("stream", response.status_code)
        response.raise_for_status()
        body = "".join(response.iter_text())

    for line in body.splitlines():
        if line.startswith("event: "):
            events.append(line.removeprefix("event: "))
    print("events", ",".join(events))
    required = ["user_message", "assistant_start", "delta", "assistant_done", "done"]
    missing = [event for event in required if event not in events]
    if missing:
        raise SystemExit(f"missing events: {missing}")

    messages_response = client.get(f"/api/agent/sessions/{session_id}/messages")
    print("messages", messages_response.status_code)
    messages_response.raise_for_status()
    messages = messages_response.json()["items"]
    if len(messages) < 2 or messages[-1]["role"] != "assistant" or not messages[-1]["content"].strip():
        raise SystemExit("streamed assistant message was not saved")


if __name__ == "__main__":
    main()
