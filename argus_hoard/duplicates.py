"""Exact and near duplicate grouping, and keeper selection.

Read-only: Argus never deletes or moves anything. The UI offers "Open
folder" and "Copy list" on top of what this module computes.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .phash import ChunkIndex, UnionFind, DEFAULT_THRESHOLD


@dataclass
class PhotoRow:
    id: str
    path: str
    size: int
    width: int | None
    height: int | None
    taken_at: str | None
    content_hash: str
    phash: int | None


@dataclass
class DuplicateGroup:
    kind: str  # "exact" | "near"
    photo_ids: list[str]
    keeper_id: str
    max_distance: int = 0


def _pick_keeper(rows: list[PhotoRow]) -> str:
    def key(r: PhotoRow):
        mp = (r.width or 0) * (r.height or 0)
        # largest resolution, then oldest taken_at, then shortest path
        taken = r.taken_at or "9999"
        return (-mp, taken, len(r.path))

    return sorted(rows, key=key)[0].id


def exact_duplicate_groups(rows: list[PhotoRow]) -> list[DuplicateGroup]:
    by_hash: dict[str, list[PhotoRow]] = defaultdict(list)
    for r in rows:
        by_hash[r.content_hash].append(r)
    groups = []
    for rows_group in by_hash.values():
        if len(rows_group) > 1:
            groups.append(
                DuplicateGroup(
                    kind="exact",
                    photo_ids=[r.id for r in rows_group],
                    keeper_id=_pick_keeper(rows_group),
                )
            )
    return groups


def near_duplicate_groups(rows: list[PhotoRow], threshold: int = DEFAULT_THRESHOLD) -> list[DuplicateGroup]:
    hashed = [r for r in rows if r.phash is not None]
    index = ChunkIndex()
    for r in hashed:
        index.add(r.id, r.phash)
    uf = UnionFind()
    by_id = {r.id: r for r in hashed}
    max_dist: dict[str, int] = {}
    for r in hashed:
        for other_id, dist in index.find(r.phash, threshold=threshold, exclude=r.id):
            uf.union(r.id, other_id)
    groups = []
    for members in uf.groups().values():
        if len(members) < 2:
            continue
        member_rows = [by_id[m] for m in members]
        # exclude groups that are actually pure exact duplicates (distance 0
        # and identical hash) -- those are reported by exact_duplicate_groups
        hashes = {r.content_hash for r in member_rows}
        if len(hashes) == 1:
            continue
        worst = 0
        ids = [r.id for r in member_rows]
        for i, a in enumerate(member_rows):
            for b in member_rows[i + 1 :]:
                from .phash import hamming

                worst = max(worst, hamming(a.phash, b.phash))
        groups.append(
            DuplicateGroup(kind="near", photo_ids=ids, keeper_id=_pick_keeper(member_rows), max_distance=worst)
        )
    return groups
