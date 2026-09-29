"""Human-readable exports from directing_package.json."""

from __future__ import annotations

import json
from pathlib import Path


def render_vo_script_md(package: dict) -> str:
    title = package.get("recommended_title") or package.get("title") or "Untitled"
    lines = [
        f"# VO script: {title}",
        "",
        f"Chapter: {package.get('chapter', '—')}",
        f"Runtime target: {package.get('runtime_target_seconds', '?')} s",
        "",
    ]
    brief = package.get("chapter_brief") or {}
    if brief.get("core_question"):
        lines.extend([f"**Core question:** {brief['core_question']}", ""])

    for row in package.get("script") or []:
        lines.append(f"## {row.get('time_start', '?')} – {row.get('time_end', '?')} ({row.get('beat_label', '')})")
        lines.append("")
        lines.append(row.get("vo") or "")
        if row.get("on_screen"):
            lines.append("")
            lines.append(f"*On screen:* {row['on_screen']}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_story_overview_md(package: dict) -> str:
    title = package.get("recommended_title") or package.get("title") or "Untitled"
    lines = [
        f"# Story overview: {title}",
        "",
        package.get("style_guide", ""),
        "",
        "## Beat sheet",
        "",
    ]
    for b in package.get("beat_sheet") or []:
        lines.append(
            f"- **{b.get('label')}** ({b.get('time_start')}–{b.get('time_end')}) — music {b.get('music_intensity', '—')}"
        )
    lines.extend(["", "## Turns", ""])
    for t in package.get("turn_ledger") or []:
        lines.append(f"- {t.get('turn_id')} @ {t.get('timestamp')}: {t.get('change')}")
    lines.extend(["", "## Plant / payoff", ""])
    for pp in package.get("plant_payoff") or []:
        lines.append(f"- Plant: {pp.get('plant')} → payoff at {pp.get('payoff_beat')}")
    lines.extend(["", "## Title options", ""])
    for t in package.get("titles") or []:
        lines.append(f"- {t}")
    if package.get("recommended_title"):
        lines.append(f"\n**Recommended:** {package['recommended_title']}")
    return "\n".join(lines).strip() + "\n"


def export_directing_artifacts(package_path: Path, out_dir: Path) -> None:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "story_overview.md").write_text(render_story_overview_md(package), encoding="utf-8")
    (out_dir / "vo_script.md").write_text(render_vo_script_md(package), encoding="utf-8")
