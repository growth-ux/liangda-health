from pathlib import Path

import requests


class CloudOcrClient:
    def __init__(self, endpoint: str | None, api_key: str | None = None):
        self.endpoint = endpoint
        self.api_key = api_key

    def extract_pages(self, path: Path) -> list[str]:
        if not self.endpoint:
            raise RuntimeError("扫描版 PDF 需要配置云 OCR 服务")

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        with path.open("rb") as file:
            response = requests.post(
                self.endpoint,
                headers=headers,
                files={"file": (path.name, file, "application/pdf")},
                timeout=120,
            )
        response.raise_for_status()
        data = response.json()
        pages = data.get("pages")
        if not isinstance(pages, list):
            raise RuntimeError("云 OCR 响应缺少 pages 字段")
        return [str(page.get("text", "")) if isinstance(page, dict) else str(page) for page in pages]
