from pathlib import Path


class PdfExtractor:
    def extract_pages(self, path: Path) -> list[str]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to extract PDF text") from exc

        pages: list[str] = []
        with fitz.open(path) as document:
            for page in document:
                pages.append(page.get_text("text").strip())
        return pages

    def render_first_page_thumbnail(self, path: Path, output_path: Path) -> None:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to render PDF thumbnails") from exc

        with fitz.open(path) as document:
            if document.page_count == 0:
                raise RuntimeError("PDF 没有可渲染页面")
            page = document[0]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(0.45, 0.45), alpha=False)
            pixmap.save(output_path)
