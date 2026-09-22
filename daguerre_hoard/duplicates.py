"""Exact and near duplicate grouping, and keeper selection.

Read-only: Daguerre never deletes or moves anything. The UI offers "Open
folder" and "Copy list" on top of what this module computes.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from .phash import DEFAULT_THRESHOLD, ChunkIndex, UnionFind, hamming

# A2 (live report): the shortest-path tie-break alone kept the backup copy
# in all 15 exact-duplicate groups ("Copia movil 2024/IMG_1.jpg" is
# shorter than "Camera Roll/2024/07/IMG_1.jpg"). A path whose folder name
# says it is a copy is now pushed to the back before path length decides.
_BACKUP_LIKE_RE = re.compile(r"(backup|copia|copy|whatsapp)", re.IGNORECASE)


def _looks_like_backup_path(path: str) -> bool:
    folded = unicodedata.normalize("NFKD", path)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return bool(_BACKUP_LIKE_RE.search(folded))


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
    mtime_ns: int = 0


@dataclass
class DuplicateGroup:
    kind: str  # "exact" | "near"
    photo_ids: list[str]
    keeper_id: str
    max_distance: int = 0


def _pick_keeper(rows: list[PhotoRow]) -> str:
    def key(r: PhotoRow):
        mp = (r.width or 0) * (r.height or 0)
        # largest resolution, then oldest taken_at, then earliest file
        # mtime, away from backup/copy/WhatsApp-looking folders, then
        # shortest path (A2: exact duplicates all have the same taken_at,
        # so path length used to be the only real tie-break).
        taken = r.taken_at or "9999"
        return (-mp, taken, r.mtime_ns, _looks_like_backup_path(r.path), len(r.path))

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
                worst = max(worst, hamming(a.phash, b.phash))
        groups.append(
            DuplicateGroup(kind="near", photo_ids=ids, keeper_id=_pick_keeper(member_rows), max_distance=worst)
        )
    return groups
