from app.services.chunker import chunk_page_text


def test_chunk_page_text_splits_structured_report_sections():
    text = "\n\n".join(
        [
            "基本信息\n姓名：陈雨微\n性别：女\n年龄：32",
            "血常规\n白细胞：5.2\n红细胞：4.1\n血红蛋白：128",
            "肝功能\n谷丙转氨酶：22\n谷草转氨酶：19",
        ]
    )

    chunks = chunk_page_text("doc_1", 2, text, chunk_size=120, overlap=20)

    assert len(chunks) == 3
    assert chunks[0].document_id == "doc_1"
    assert chunks[0].page_no == 2
    assert chunks[0].content.startswith("基本信息")
    assert chunks[1].content.startswith("血常规")
    assert chunks[2].content.startswith("肝功能")


def test_chunk_page_text_splits_long_section_with_langchain_overlap():
    text = "体检总结：" + "一" * 220

    chunks = chunk_page_text("doc_1", 1, text, chunk_size=120, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 120 for chunk in chunks)
    assert chunks[0].content[-20:] == chunks[1].content[:20]


def test_chunk_page_text_ignores_blank_text():
    chunks = chunk_page_text("doc_1", 1, "   \n\t  ")

    assert chunks == []
