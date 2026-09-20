"""Map storyboard scene ids (SC01) to on-disk cinematic ids (S01)."""

from __future__ import annotations


def scene_id_aliases(scene_id: str) -> list[str]:
    """Return ids to try when resolving cinematic asset paths."""
    out: list[str] = [scene_id]
    if scene_id.startswith("SC") and scene_id[2:].isdigit():
        n = int(scene_id[2:])
        out.append(f"S{n:02d}")
        out.append(f"S{n}")
    elif scene_id.startswith("S") and len(scene_id) > 1 and scene_id[1:].isdigit():
        n = int(scene_id[1:])
        out.append(f"SC{n:02d}")
        out.append(f"S{n:02d}")
    deduped: list[str] = []
    for item in out:
        if item not in deduped:
            deduped.append(item)
    return deduped
