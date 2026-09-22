from argus_hoard.duplicates import PhotoRow, exact_duplicate_groups, near_duplicate_groups


def _row(id, path, size, w, h, taken_at, content_hash, phash=None):
    return PhotoRow(id=id, path=path, size=size, width=w, height=h, taken_at=taken_at, content_hash=content_hash, phash=phash)


def test_exact_duplicate_keeper_prefers_largest_resolution():
    rows = [
        _row("a", "/x/small.jpg", 100, 100, 100, "2020-01-01", "hash1"),
        _row("b", "/x/big.jpg", 500, 800, 600, "2020-01-02", "hash1"),
        _row("c", "/other/unique.jpg", 300, 200, 200, "2020-01-01", "hash2"),
    ]
    groups = exact_duplicate_groups(rows)
    assert len(groups) == 1
    assert groups[0].keeper_id == "b"
    assert set(groups[0].photo_ids) == {"a", "b"}


def test_exact_duplicate_keeper_ties_use_oldest_then_shortest_path():
    rows = [
        _row("a", "/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg", 100, 800, 600, "2020-06-01", "hash1"),
        _row("b", "/b.jpg", 100, 800, 600, "2020-06-01", "hash1"),
    ]
    groups = exact_duplicate_groups(rows)
    assert groups[0].keeper_id == "b"  # shorter path wins the tie


def test_near_duplicate_grouping_by_phash():
    rows = [
        _row("a", "/x/a.jpg", 100, 800, 600, "2020-01-01", "h1", phash=0b0),
        _row("b", "/x/b.jpg", 100, 800, 600, "2020-01-02", "h2", phash=0b101),  # distance 2 from a
        _row("c", "/x/c.jpg", 100, 800, 600, "2020-01-03", "h3", phash=0xFFFFFFFFFFFFFFFF),  # distance 64 from a
    ]
    groups = near_duplicate_groups(rows, threshold=6)
    assert len(groups) == 1
    assert set(groups[0].photo_ids) == {"a", "b"}
    assert groups[0].max_distance == 2
