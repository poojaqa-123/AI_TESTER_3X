"""Reciprocal Rank Fusion — combines the dense and sparse rank lists into one
ordering without needing to calibrate the two very different score scales."""

from . import config


def rrf_fuse(rank_lists: list[list[int]], k: int = None) -> list[tuple[int, float]]:
    k = k if k is not None else config.RRF_K
    scores: dict[int, float] = {}
    for ranked_ids in rank_lists:
        for rank, point_id in enumerate(ranked_ids, start=1):
            scores[point_id] = scores.get(point_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
