"""Qdrant wrapper. Runs embedded (local file store, no Docker) by default;
set QDRANT_URL to point at a real server instead.
"""

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from . import config

_client = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if config.QDRANT_URL:
            _client = QdrantClient(url=config.QDRANT_URL)
        else:
            _client = QdrantClient(path=config.QDRANT_PATH)
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


def upsert_chunks(chunks, dense_vecs, sparse_vecs, start_id: int = 0):
    client = get_client()
    points = []
    for i, chunk in enumerate(chunks):
        indices, values = sparse_vecs[i]
        payload = {
            **{k: v for k, v in chunk.meta.items() if v is not None},
            "text": chunk.text,
            "row_index": chunk.row_index,
            "chunk_index": chunk.chunk_index,
            "chunk_id": chunk.chunk_id,
        }
        points.append(
            qm.PointStruct(
                id=start_id + i,
                vector={"dense": dense_vecs[i], "sparse": qm.SparseVector(indices=indices, values=values)},
                payload=payload,
            )
        )
    client.upsert(collection_name=config.QDRANT_COLLECTION, points=points)


def dense_search(query_vec: list[float], limit: int):
    client = get_client()
    res = client.query_points(
        collection_name=config.QDRANT_COLLECTION,
        query=query_vec,
        using="dense",
        limit=limit,
        with_payload=True,
    )
    return res.points


def sparse_search(indices: list[int], values: list[float], limit: int):
    client = get_client()
    res = client.query_points(
        collection_name=config.QDRANT_COLLECTION,
        query=qm.SparseVector(indices=indices, values=values),
        using="sparse",
        limit=limit,
        with_payload=True,
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
        "mode": "server" if config.QDRANT_URL else "embedded",
        "path": None if config.QDRANT_URL else config.QDRANT_PATH,
    }


def scroll_chunks(limit: int = 50, offset=None, search: str = None, filters: dict = None):
    client = get_client()
    must = []
    if filters:
        for key, val in filters.items():
            if val:
                must.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=val)))
    q_filter = qm.Filter(must=must) if must else None

    if search:
        # substring search isn't a native Qdrant filter; scan the collection.
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
