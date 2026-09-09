"""Qdrant wrapper. Defaults to a standalone Qdrant service (QDRANT_URL, e.g. the
`qdrant` container in docker-compose.yml) so multiple gunicorn workers can share
one index. Set QDRANT_PATH instead for local single-process embedded mode.
"""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from . import config

# Fixed namespace for deterministic point ids — re-ingesting the same source
# with the same chunk_ids overwrites the same points (upsert) instead of
# accumulating duplicates or needing manual id-offset bookkeeping.
_ID_NAMESPACE = uuid.UUID("6f6b6e1a-7b8a-4a3a-9b3b-0f2f6d1c9a10")


def point_id(source_name: str, chunk_id: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, f"{source_name}:{chunk_id}"))

_client = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if config.QDRANT_PATH:
            _client = QdrantClient(path=config.QDRANT_PATH)
        else:
            _client = QdrantClient(url=config.QDRANT_URL)
    return _client


def collection_exists() -> bool:
    return get_client().collection_exists(config.QDRANT_COLLECTION)


def ensure_collection(dim: int, recreate: bool = False):
    client = get_client()
    exists = client.collection_exists(config.QDRANT_COLLECTION)
    if exists and recreate:
        client.delete_collection(config.QDRANT_COLLECTION)
        exists = False
    if not exists:
        client.create_collection(
            collection_name=config.QDRANT_COLLECTION,
            vectors_config={"dense": qm.VectorParams(size=dim, distance=qm.Distance.COSINE)},
            sparse_vectors_config={"sparse": qm.SparseVectorParams()},
        )
    return client


def upsert_chunks(chunks, dense_vecs, sparse_vecs):
    client = get_client()
    points = []
    for i, chunk in enumerate(chunks):
        indices, values = sparse_vecs[i]
        payload = {
            **{k: v for k, v in chunk.meta.items() if v is not None},
            "text": chunk.text,
            "source_type": chunk.source_type,
            "source_name": chunk.source_name,
            "row_index": chunk.row_index,
            "chunk_index": chunk.chunk_index,
            "chunk_id": chunk.chunk_id,
        }
        points.append(
            qm.PointStruct(
                id=point_id(chunk.source_name, chunk.chunk_id),
                vector={"dense": dense_vecs[i], "sparse": qm.SparseVector(indices=indices, values=values)},
                payload=payload,
            )
        )
    client.upsert(collection_name=config.QDRANT_COLLECTION, points=points)


def _source_type_filter(source_types: list[str] | None) -> qm.Filter | None:
    if not source_types:
        return None
    return qm.Filter(must=[qm.FieldCondition(key="source_type", match=qm.MatchAny(any=source_types))])


def dense_search(query_vec: list[float], limit: int, source_types: list[str] | None = None):
    client = get_client()
    res = client.query_points(
        collection_name=config.QDRANT_COLLECTION,
        query=query_vec,
        using="dense",
        limit=limit,
        with_payload=True,
        query_filter=_source_type_filter(source_types),
    )
    return res.points


def sparse_search(indices: list[int], values: list[float], limit: int, source_types: list[str] | None = None):
    client = get_client()
    res = client.query_points(
        collection_name=config.QDRANT_COLLECTION,
        query=qm.SparseVector(indices=indices, values=values),
        using="sparse",
        limit=limit,
        with_payload=True,
        query_filter=_source_type_filter(source_types),
    )
    return res.points


def collection_info() -> dict:
    client = get_client()
    if not client.collection_exists(config.QDRANT_COLLECTION):
        return {"exists": False, "points_count": 0}
    info = client.get_collection(config.QDRANT_COLLECTION)
    return {
        "exists": True,
        "points_count": info.points_count,
        "status": str(info.status),
        "collection": config.QDRANT_COLLECTION,
        "mode": "embedded" if config.QDRANT_PATH else "server",
        "url": None if config.QDRANT_PATH else config.QDRANT_URL,
    }


def counts_by_source_type() -> dict:
    client = get_client()
    if not client.collection_exists(config.QDRANT_COLLECTION):
        return {}
    counts = {}
    for source_type in set(config.SOURCE_FOLDERS.values()):
        result = client.count(
            collection_name=config.QDRANT_COLLECTION,
            count_filter=_source_type_filter([source_type]),
        )
        counts[source_type] = result.count
    return counts


def count_for_source_name(source_name: str) -> int:
    client = get_client()
    if not client.collection_exists(config.QDRANT_COLLECTION):
        return 0
    result = client.count(
        collection_name=config.QDRANT_COLLECTION,
        count_filter=qm.Filter(must=[qm.FieldCondition(key="source_name", match=qm.MatchValue(value=source_name))]),
    )
    return result.count


def delete_by_source_name(source_name: str):
    client = get_client()
    if not client.collection_exists(config.QDRANT_COLLECTION):
        return
    client.delete(
        collection_name=config.QDRANT_COLLECTION,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(must=[qm.FieldCondition(key="source_name", match=qm.MatchValue(value=source_name))])
        ),
    )


def scroll_chunks(limit: int = 50, offset=None, search: str = None, filters: dict = None):
    client = get_client()
    must = []
    if filters:
        for key, val in filters.items():
            if val:
                must.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=val)))
    q_filter = qm.Filter(must=must) if must else None

    if search:
        all_points, _ = client.scroll(
            collection_name=config.QDRANT_COLLECTION,
            limit=10000,
            with_payload=True,
            with_vectors=True,
            scroll_filter=q_filter,
        )
        matched = [p for p in all_points if search.lower() in str(p.payload.get("text", "")).lower()]
        start = offset or 0
        return matched[start:start + limit], (start + limit if start + limit < len(matched) else None)

    points, next_offset = client.scroll(
        collection_name=config.QDRANT_COLLECTION,
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=True,
        scroll_filter=q_filter,
    )
    return points, next_offset


def get_points_by_ids(ids: list[int]):
    client = get_client()
    if not ids:
        return []
    return client.retrieve(collection_name=config.QDRANT_COLLECTION, ids=ids, with_payload=True)
