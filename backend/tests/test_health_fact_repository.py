from app.models.health_fact import HealthFact
from app.repositories.health_fact_repository import HealthFactCreate, SqlAlchemyHealthFactRepository


def _fact(**overrides):
    data = {
        "fact_id": "fact_1",
        "member_id": "mem_1",
        "fact_type": "risk",
        "name": "血脂偏高",
        "value": None,
        "unit": None,
        "reference_range": None,
        "status": "warning",
        "source_document_id": "doc_1",
        "source_page_no": 2,
        "source_chunk_id": None,
        "evidence_text": "总胆固醇高于参考范围",
    }
    data.update(overrides)
    return HealthFactCreate(**data)


def test_health_fact_repository_saves_and_lists_by_document(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)

    repository.save_facts([_fact(source_chunk_id="chunk_1")])

    facts = repository.list_by_document("doc_1")
    assert len(facts) == 1
    assert facts[0].fact_id == "fact_1"
    assert facts[0].member_id == "mem_1"
    assert facts[0].fact_type == "risk"
    assert facts[0].name == "血脂偏高"
    assert facts[0].reference_range is None
    assert facts[0].status == "warning"
    assert facts[0].source_page_no == 2
    assert facts[0].source_chunk_id == "chunk_1"
    assert facts[0].evidence_text == "总胆固醇高于参考范围"


def test_health_fact_repository_lists_by_member(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)
    repository.save_facts(
        [
            _fact(fact_id="fact_1", member_id="mem_1", source_document_id="doc_1"),
            _fact(fact_id="fact_2", member_id="mem_2", source_document_id="doc_2"),
        ]
    )

    facts = repository.list_by_member("mem_1")

    assert [fact.fact_id for fact in facts] == ["fact_1"]


def test_health_fact_repository_keeps_source_chunk_optional(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)

    repository.save_facts([_fact(source_chunk_id=None)])

    fact = repository.list_by_document("doc_1")[0]
    assert fact.source_chunk_id is None


def test_health_fact_repository_deletes_by_document(db_session):
    repository = SqlAlchemyHealthFactRepository(db_session)
    repository.save_facts([_fact()])

    repository.delete_by_document("doc_1")

    assert db_session.query(HealthFact).filter(HealthFact.source_document_id == "doc_1").all() == []
