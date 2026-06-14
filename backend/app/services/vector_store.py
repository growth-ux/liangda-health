from dataclasses import dataclass


@dataclass(frozen=True)
class VectorRecord:
    chunk_id: str
    document_id: str
    member_id: str
    embedding: list[float]


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    score: float


class MilvusVectorStore:
    def __init__(
        self,
        uri: str,
        collection_name: str,
        dimension: int,
        token: str | None = None,
    ):
        from pymilvus import DataType, MilvusClient

        self.collection_name = collection_name
        self.dimension = dimension
        self.client = MilvusClient(uri=uri, token=token)
        if not self.client.has_collection(collection_name):
            schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=64)
            schema.add_field("document_id", DataType.VARCHAR, max_length=64)
            schema.add_field("member_id", DataType.VARCHAR, max_length=64)
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dimension)

            index_params = MilvusClient.prepare_index_params()
            index_params.add_index(
                field_name="embedding",
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )

            self.client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
            )

    def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        self.client.upsert(
            collection_name=self.collection_name,
            data=[
                {
                    "chunk_id": record.chunk_id,
                    "document_id": record.document_id,
                    "member_id": record.member_id,
                    "embedding": record.embedding,
                }
                for record in records
            ],
        )
        self.client.flush(self.collection_name)

    def search(self, query_embedding: list[float], top_k: int, member_id: str | None = None) -> list[VectorHit]:
        if member_id is None:
            raise ValueError("member_id is required for search")
        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            limit=top_k,
            filter=f'member_id == "{member_id}"',
            output_fields=["chunk_id"],
        )
        hits: list[VectorHit] = []
        for result in results[0]:
            chunk_id = result.get("entity", {}).get("chunk_id") or result.get("id")
            hits.append(VectorHit(chunk_id=chunk_id, score=float(result.get("distance", 0.0))))
        return hits
