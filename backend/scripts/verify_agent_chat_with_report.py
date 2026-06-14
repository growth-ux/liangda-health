from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def main() -> None:
    if not settings.llm_api_key:
        raise SystemExit("HEALTH_AGENT_LLM_API_KEY is required")

    app = create_app()
    client = TestClient(app)
    pdf_path = _make_pdf()

    with pdf_path.open("rb") as file:
        upload_response = client.post(
            "/api/kb/upload",
            files={"file": ("agent-report.pdf", file, "application/pdf")},
        )
    print("upload", upload_response.status_code)
    upload_response.raise_for_status()

    session_response = client.post("/api/agent/sessions", json={"title": "新对话"})
    print("create_session", session_response.status_code)
    session_response.raise_for_status()
    session_id = session_response.json()["session_id"]

    send_response = client.post(
        f"/api/agent/sessions/{session_id}/messages:send",
        json={"content": "我妈这份报告有什么异常？请用三点简短说明。"},
    )
    print("send", send_response.status_code)
    send_response.raise_for_status()
    assistant = send_response.json()["assistant_message"]["content"]
    print("assistant_preview", assistant[:160])
    if not assistant.strip():
        raise SystemExit("assistant response is empty")


def _make_pdf() -> Path:
    import fitz

    path = Path(tempfile.mkdtemp()) / "agent-report.pdf"
    text = (
        "General Check Report\n"
        "Patient: Mother\n"
        "Exam Date: 2026-05-12\n"
        "Institution: CityHospital\n"
        "Blood pressure systolic 152 mmHg, high\n"
        "Bone density T score -2.1, low bone mass\n"
        + "health report body " * 30
    )
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()
    return path


if __name__ == "__main__":
    main()
