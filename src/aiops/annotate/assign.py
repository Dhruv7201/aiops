"""Image-to-user assignment logic (pure)."""

from __future__ import annotations


def round_robin_assign(
    filenames: list[str],
    users: list[str],
    existing: dict[str, str] | None = None,
    keep_existing: bool = True,
) -> dict[str, str]:
    """Deterministically divide images among users round-robin.

    With keep_existing=True, images already assigned (to any user) keep
    their assignment and only unassigned images are distributed.
    """
    if not users:
        raise ValueError("at least one user is required")

    existing = existing or {}
    result: dict[str, str] = {}
    if keep_existing:
        result.update({f: u for f, u in existing.items() if f in filenames})

    pending = [f for f in sorted(filenames) if f not in result]
    for i, filename in enumerate(pending):
        result[filename] = users[i % len(users)]
    return result
