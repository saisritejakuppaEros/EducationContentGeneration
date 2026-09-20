#!/usr/bin/env python3
"""QC report, visual scoring, and HTML contact sheet before final cut."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import base64
import json
import subprocess
import tempfile

from composition_validator import resolve_shot_video, validate_production
from director_checklist import validate_storyboard_director
from paths import PROJECT_ROOT, add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel
from pipeline_utils import write_gate, write_json
from visual_qa import score_shot_video

SUB_MODULE = "pipeline"


def extract_thumb(video: Path) -> str | None:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        out = Path(tmp.name)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        "0.5",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        "4",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not out.is_file():
        out.unlink(missing_ok=True)
        return None
    data = base64.b64encode(out.read_bytes()).decode("ascii")
    out.unlink(missing_ok=True)
    return f"data:image/jpeg;base64,{data}"


def build_contact_sheet(storyboard: dict, assets_root: Path, scores: dict[tuple[str, int], dict]) -> Path:
    rows = []
    cinematic_dir = assets_root / "cinematic_videos"
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        for shot in scene.get("shots", []):
            shot_num = int(shot.get("shot") or 0)
            video = resolve_shot_video(scene_id=scene_id, shot_num=shot_num, cinematic_dir=cinematic_dir)
            key = (scene_id, shot_num)
            qc = scores.get(key, {})
            thumb = extract_thumb(video) if video else None
            img = f'<img src="{thumb}" width="240"/>' if thumb else "<em>missing</em>"
            rows.append(
                f"<tr><td>{scene_id}</td><td>{shot_num}</td><td>{shot.get('type','')}</td>"
                f"<td>{qc.get('score','—')}</td><td>{', '.join(qc.get('reasons') or [])}</td>"
                f"<td>{img}</td><td>{(shot.get('dialogue') or '')[:80]}</td></tr>"
            )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Shot contact sheet</title>
<style>
body{{font-family:system-ui;background:#111;color:#eee;padding:1rem}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #333;padding:6px;vertical-align:top;font-size:13px}}
th{{background:#222}}
</style></head><body>
<h1>Production contact sheet</h1>
<p>{project_rel(assets_root)}</p>
<table><tr><th>Scene</th><th>Shot</th><th>Type</th><th>QC</th><th>Notes</th><th>Frame</th><th>Dialogue</th></tr>
{''.join(rows)}
</table></body></html>"""
    out = output_dir(SUB_MODULE) / "contact_sheet.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate assets and score cinematic shots.")
    parser.add_argument("--storyboard", type=Path, default=None)
    parser.add_argument("--assets-root", type=Path, default=None)
    parser.add_argument("--enable-manim", action="store_true")
    parser.add_argument("--fail-on-error", action="store_true")
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    assets_root = args.assets_root or get_output_root()
    storyboard_path = args.storyboard or assets_root / "storyboard" / "storyboard.json"
    if not storyboard_path.is_file():
        raise FileNotFoundError(storyboard_path)

    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    validation = validate_production(
        storyboard=storyboard,
        assets_root=assets_root,
        enable_manim=args.enable_manim,
    )
    director = validate_storyboard_director(storyboard)

    cinematic_dir = assets_root / "cinematic_videos"
    scores: dict[tuple[str, int], dict] = {}
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        for shot in scene.get("shots", []):
            shot_num = int(shot.get("shot") or 0)
            video = resolve_shot_video(scene_id=scene_id, shot_num=shot_num, cinematic_dir=cinematic_dir)
            if not video:
                continue
            scores[(scene_id, shot_num)] = score_shot_video(
                video, expected_duration=float(shot.get("duration_seconds") or 5)
            )

    sheet_path = build_contact_sheet(storyboard, assets_root, scores)
    report = {
        "composition": validation,
        "director_checklist": director,
        "shot_scores": [
            {"scene_id": k[0], "shot": k[1], **v} for k, v in sorted(scores.items())
        ],
        "contact_sheet": str(sheet_path.relative_to(PROJECT_ROOT)),
    }
    report_path = output_dir(SUB_MODULE) / "qc_report.json"
    write_json(report_path, report)

    passed = validation["passed"] and director["passed"]
    write_gate(
        "production_qc",
        passed=passed,
        notes=f"errors={validation['error_count']} warnings={validation['warning_count']}",
        details={"report": str(report_path.relative_to(PROJECT_ROOT))},
    )

    print(f"QC report: {project_rel(report_path)}")
    print(f"Contact sheet: {project_rel(sheet_path)}")
    print(f"Passed: {passed} ({validation['shots_ok']}/{validation['shots_checked']} shots OK)")

    if args.fail_on_error and not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
