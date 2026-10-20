"""Compare two labellings of the same memo: the shared logic behind tools/compare.py and tools/merge.py."""

from .records import entity_key


def normalise(memo):
    """span key -> (attrs, owner key, anchor key), with pointers expressed as target offsets."""
    by_id = {s.id: s for s in memo.spans}
    pointer_key = lambda target_id: None if target_id is None else entity_key(memo.spans, by_id[target_id])
    return {(s.type, s.start, s.end): (tuple(sorted(s.attrs.items())), pointer_key(s.owner), pointer_key(s.anchor)) for s in memo.spans}


def describe(memo):
    by_id = {s.id: s for s in memo.spans}
    lines = []
    for s in memo.spans:
        parts = [f"{s.type} {s.text!r}@{s.start}"]
        parts += [f"{k}={v}" for k, v in s.attrs.items()]
        parts += [f"{p}->{by_id[getattr(s, p)].text!r}@{by_id[getattr(s, p)].start}" for p in ("owner", "anchor") if getattr(s, p)]
        lines.append(" ".join(parts))
    return lines


def diff_kinds(a, b):
    kinds = []
    for key in a.keys() | b.keys():
        if key not in b or key not in a:
            same_place = [k for k in (b if key in a else a) if k[1] < key[2] and key[1] < k[2]]
            if not same_place:
                kinds.append(f"{'missing' if key in a else 'extra'}:{key[0]}")
            elif any(k[0] == key[0] for k in same_place):
                kinds.append(f"boundary:{key[0]}")
            else:
                kinds.append(f"type:{key[0]}")
            continue

        (attrs_a, owner_a, anchor_a), (attrs_b, owner_b, anchor_b) = a[key], b[key]
        kinds += [f"attr:{k}" for (k, v) in attrs_a if dict(attrs_b).get(k) != v]
        if owner_a != owner_b:
            kinds.append(f"owner:{key[0]}")
        if anchor_a != anchor_b:
            kinds.append(f"anchor:{key[0]}")
    return sorted(set(kinds))
