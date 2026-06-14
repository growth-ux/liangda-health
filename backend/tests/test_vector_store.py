from app.services.vector_store import InMemoryVectorStore, VectorRecord


def test_in_memory_vector_store_filters_by_member_id():
    store = InMemoryVectorStore()
    store.upsert([
        VectorRecord(chunk_id="c1", document_id="d1", member_id="mem_1", embedding=[1.0, 0.0]),
        VectorRecord(chunk_id="c2", document_id="d2", member_id="mem_2", embedding=[1.0, 0.0]),
    ])

    hits = store.search([1.0, 0.0], top_k=5, member_id="mem_1")

    assert [hit.chunk_id for hit in hits] == ["c1"]


def test_in_memory_vector_store_returns_empty_when_no_match():
    store = InMemoryVectorStore()
    store.upsert([
        VectorRecord(chunk_id="c1", document_id="d1", member_id="mem_1", embedding=[1.0, 0.0]),
    ])

    hits = store.search([1.0, 0.0], top_k=5, member_id="mem_2")

    assert hits == []


def test_vector_record_requires_member_id():
    record = VectorRecord(chunk_id="c1", document_id="d1", member_id="mem_1", embedding=[1.0])
    assert record.member_id == "mem_1"
