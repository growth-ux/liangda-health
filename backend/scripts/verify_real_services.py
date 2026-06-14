from pathlib import Path
import os
import tempfile

from fastapi.testclient import TestClient

from app.main import create_app


def main() -> None:
    pdf_path = _make_pdf()
    app = create_app()
    client = TestClient(app)

    with pdf_path.open("rb") as file:
        upload_response = client.post(
            "/api/kb/upload",
            files={"file": ("real-services-report.pdf", file, "application/pdf")},
        )
    print("upload", upload_response.status_code, upload_response.json())
    upload_response.raise_for_status()
    if upload_response.json()["status"] != "ready":
        raise SystemExit("upload did not finish as ready")

    list_response = client.get("/api/kb/documents")
    print("documents", list_response.status_code, list_response.json()[:1])
    list_response.raise_for_status()

    search_response = client.post("/api/kb/search", json={"query": "Bone density", "top_k": 3})
    print("search", search_response.status_code, search_response.json())
    search_response.raise_for_status()
    if not search_response.json()["items"]:
        raise SystemExit("search returned no items")


def _make_pdf() -> Path:
    import fitz

    path = Path(tempfile.mkdtemp()) / "real-services-report.pdf"
    text = (
        "General Check Report\n"
        "Name: RealServiceUser\n"
        "Exam Date: 2026-05-12\n"
        "Institution: CityHospital\n"
        "Bone density T score -2.1\n"
        + "report body " * 30
    )
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()
    return path


if __name__ == "__main__":
    os.environ.setdefault("HEALTH_AGENT_MILVUS_ENABLED", "true")
    main()
