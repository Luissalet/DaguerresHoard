import random

from argus_hoard.phash import ChunkIndex, UnionFind, hamming


def _flip_bits(value: int, n: int, rng: random.Random) -> int:
    bits = rng.sample(range(64), n)
    for b in bits:
        value ^= 1 << b
    return value


def test_chunk_index_matches_brute_force_sample():
    rng = random.Random(42)
    base_values = {f"p{i}": rng.getrandbits(64) for i in range(300)}
    # Create some near-duplicate pairs with small bit flips.
    pairs = []
    for i in range(20):
        base_id = f"p{i}"
        near_id = f"near{i}"
        near_val = _flip_bits(base_values[base_id], rng.randint(1, 6), rng)
        base_values[near_id] = near_val
        pairs.append((base_id, near_id))

    index = ChunkIndex()
    for k, v in base_values.items():
        index.add(k, v)

    threshold = 6
    for base_id, near_id in pairs:
        found_ids = {cid for cid, _ in index.find(base_values[base_id], threshold=threshold, exclude=base_id)}
        brute = {
            cid
            for cid, v in base_values.items()
            if cid != base_id and hamming(v, base_values[base_id]) <= threshold
        }
        assert found_ids == brute
        assert near_id in found_ids


def test_union_find_groups():
    uf = UnionFind()
    uf.union("a", "b")
    uf.union("b", "c")
    uf.union("x", "y")
    groups = uf.groups()
    group_sets = [set(v) for v in groups.values()]
    assert {"a", "b", "c"} in group_sets
    assert {"x", "y"} in group_sets
