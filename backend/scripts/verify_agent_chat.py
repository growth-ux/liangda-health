from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def main() -> None:
    if not settings.llm_api_key:
        raise SystemExit("HEALTH_AGENT_LLM_API_KEY is required")

    app = create_app()
    client = TestClient(app)

    session_response = client.post("/agent/sessions", json={"title": "新对话"})
    print("create_session", session_response.status_code)
    session_response.raise_for_status()
    session_id = session_response.json()["session_id"]

    send_response = client.post(
        f"/agent/sessions/{session_id}/messages:send",
        json={"content": "我妈这份报告有什么异常？请用三点简短说明。"},
    )
    print("send", send_response.status_code)
    send_response.raise_for_status()

    data = send_response.json()
    assistant = data["assistant_message"]["content"]
    if not assistant.strip():
        raise SystemExit("assistant response is empty")
    print("assistant_preview", assistant[:120])

    messages_response = client.get(f"/agent/sessions/{session_id}/messages")
    print("messages", messages_response.status_code)
    messages_response.raise_for_status()
    if len(messages_response.json()["items"]) < 2:
        raise SystemExit("messages were not saved")


if __name__ == "__main__":
    main()
