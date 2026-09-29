#!/usr/bin/env python3
"""
Optional addon: HTML/CSS/JS diagram inserts → MP4 (parallel to Manim stage 5b).

Does not replace default LTX keyframes. Enable with run_pipeline.py --enable-html-inserts.
Hand-authored pages: html_inserts/<scene_id>/<scene_id>_shotNN/index.html
"""
import _bootstrap  # noqa: F401

import argparse
import json
from pathlib import Path

from html_insert_render import load_series_palette, render_html_to_mp4, write_stub_html
from insert_shots import insert_html_dir, insert_mp4_path, merge_insert_shots
from paths import PROJECT_ROOT, add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel

SUB_MODULE = "html_inserts"
DEFAULT_STORYBOARD = output_dir("storyboard") / "storyboard.json"
DEFAULT_DECOMP = output_dir("shots") / "shot_decomposition.json"
DEFAULT_SERIES = output_dir("series_profile") / "series_profile.json"


def shot_brief(scene: dict, shot: dict) -> tuple[str, list[str]]:
    title = (
        shot.get("on_screen_text")
        or scene.get("on_screen_text")
        or scene.get("title")
        or shot.get("label")
        or "Diagram"
    )
    lines: list[str] = []
    for key in ("flux_prompt", "visual_description", "narration", "vo_line"):
        val = shot.get(key) or scene.get(key)
        if val and isinstance(val, str):
            lines.append(val[:240])
    if not lines:
        lines = ["Animated diagram insert"]
    return str(title), lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Render HTML diagram inserts to MP4 (optional addon).")
    parser.add_argument("--storyboard", type=Path, default=None)
    parser.add_argument("--shot-decomposition", type=Path, default=None)
    parser.add_argument("--series-profile", type=Path, default=None)
    parser.add_argument("--generate-stubs", action="store_true", help="Write stub index.html when missing.")
    parser.add_argument("--render-only", action="store_true", help="Only record existing HTML (no stub generation).")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    assets_root = get_output_root()
    out_root = output_dir(SUB_MODULE)
    out_root.mkdir(parents=True, exist_ok=True)

    storyboard_path = args.storyboard or assets_root / "storyboard" / "storyboard.json"
    decomp_path = args.shot_decomposition or assets_root / "shots" / "shot_decomposition.json"
    series_path = args.series_profile or assets_root / "series_profile" / "series_profile.json"

    storyboard = None
    if storyboard_path.is_file():
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    decomposition = None
    if decomp_path.is_file():
        decomposition = json.loads(decomp_path.read_text(encoding="utf-8"))
    if not storyboard and not decomposition:
        raise FileNotFoundError(
            f"Need storyboard or shot_decomposition under {project_rel(assets_root)}/"
        )

    palette = load_series_palette(series_path)
    pairs = merge_insert_shots(storyboard, decomposition)
    manifest_path = out_root / "manifest.json"
    manifest: dict = {"shots": [], "backend": "html_inserts"}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pending = []
    for scene, shot in pairs:
        scene_id = scene["scene_id"]
        shot_num = int(shot["shot"])
        mp4 = insert_mp4_path(out_root, scene_id, shot_num)
        if args.skip_existing and mp4.is_file():
            continue
        pending.append((scene, shot, mp4))

    if not pending:
        print("Nothing to render (all inserts exist or none matched).")
        return

    print(f"{len(pending)} HTML insert shot(s) — output: {project_rel(out_root)}/")

    if args.dry_run:
        for scene, shot, mp4 in pending:
            html_dir = insert_html_dir(out_root, scene["scene_id"], int(shot["shot"]))
            print(f"  {scene['scene_id']} shot {shot['shot']} → {project_rel(mp4)} (html: {project_rel(html_dir)}/)")
        return

    for scene, shot, mp4 in pending:
        scene_id = scene["scene_id"]
        shot_num = int(shot["shot"])
        html_dir = insert_html_dir(out_root, scene_id, shot_num)
        html_path = html_dir / "index.html"
        duration = float(shot.get("duration_seconds") or scene.get("duration_seconds") or 5.0)

        if not html_path.is_file() and args.generate_stubs and not args.render_only:
            title, lines = shot_brief(scene, shot)
            write_stub_html(
                out_html=html_path,
                title=title,
                body_lines=lines,
                duration_seconds=duration,
                series_palette=palette,
            )
            print(f"Wrote stub {project_rel(html_path)}")

        if not html_path.is_file():
            print(f"Skip {scene_id} shot {shot_num} — no {project_rel(html_path)} (use --generate-stubs)")
            entry = {
                "scene_id": scene_id,
                "shot": shot_num,
                "success": False,
                "error": "missing index.html",
                "html": None,
                "output": None,
            }
        else:
            result = render_html_to_mp4(html_path, mp4, duration_seconds=duration)
            entry = {
                "scene_id": scene_id,
                "shot": shot_num,
                "success": result["success"],
                "error": result.get("error"),
                "backend": result.get("backend"),
                "html": project_rel(html_path),
                "output": project_rel(mp4) if result["success"] else None,
            }
            if result["success"]:
                print(f"Rendered {project_rel(mp4)}")
            else:
                print(f"Failed {scene_id} shot {shot_num}: {result.get('error')}")

        manifest["shots"] = [
            e for e in manifest.get("shots", []) if not (e["scene_id"] == scene_id and e["shot"] == shot_num)
        ]
        manifest["shots"].append(entry)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Manifest: {project_rel(manifest_path)}")


if __name__ == "__main__":
    main()
