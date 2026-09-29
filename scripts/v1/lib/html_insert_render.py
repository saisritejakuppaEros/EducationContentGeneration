"""Render self-contained HTML insert pages to MP4 (optional Playwright + ffmpeg)."""

from __future__ import annotations

import html as html_module
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 24


def write_stub_html(
    *,
    out_html: Path,
    title: str,
    body_lines: list[str],
    duration_seconds: float,
    series_palette: dict[str, Any] | None = None,
) -> None:
    """Minimal animated slide when no hand-authored HTML exists yet."""
    palette = series_palette or {}
    bg = palette.get("background") or "#0f172a"
    accent = palette.get("accent") or "#38bdf8"
    text = palette.get("text") or "#f8fafc"
    safe_title = html_module.escape(title or "Diagram")
    bullets = "".join(
        f'<li class="fade" style="animation-delay:{0.4 + i * 0.35}s">'
        f"{html_module.escape(line)}</li>"
        for i, line in enumerate(body_lines[:8])
    )
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{safe_title}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; width: {DEFAULT_WIDTH}px; height: {DEFAULT_HEIGHT}px;
    background: {bg}; color: {text}; font-family: system-ui, sans-serif;
    display: flex; flex-direction: column; justify-content: center; padding: 80px;
  }}
  h1 {{ font-size: 56px; color: {accent}; margin: 0 0 32px; opacity: 0; animation: in 0.8s forwards; }}
  ul {{ font-size: 36px; line-height: 1.45; list-style: none; padding: 0; margin: 0; }}
  li {{ opacity: 0; transform: translateY(12px); }}
  li.fade {{ animation: in 0.7s forwards; }}
  @keyframes in {{ to {{ opacity: 1; transform: none; }} }}
</style>
</head>
<body>
  <h1>{safe_title}</h1>
  <ul>{bullets or "<li class='fade'>Diagram insert</li>"}</ul>
  <script>document.documentElement.dataset.duration = "{duration_seconds}";</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def _ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def webm_to_mp4(webm: Path, mp4: Path) -> None:
    mp4.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            _ffmpeg_bin(),
            "-y",
            "-i",
            str(webm),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(DEFAULT_FPS),
            str(mp4),
        ],
        check=True,
        capture_output=True,
    )


def render_html_to_mp4(
    html_path: Path,
    mp4_path: Path,
    *,
    duration_seconds: float,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> dict[str, Any]:
    """
    Record HTML to MP4. Requires Playwright + Chromium (`playwright install chromium`).
    Returns {"success": bool, "error": str | None, "backend": str}.
    """
    if not html_path.is_file():
        return {"success": False, "error": f"missing html: {html_path}", "backend": "none"}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "success": False,
            "error": "playwright not installed (pip install playwright && playwright install chromium)",
            "backend": "none",
        }

    wait_ms = max(500, int(duration_seconds * 1000))
    uri = html_path.resolve().as_uri()

    with tempfile.TemporaryDirectory(prefix="html_insert_") as tmp:
        video_dir = Path(tmp)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": width, "height": height},
                record_video_dir=str(video_dir),
                record_video_size={"width": width, "height": height},
            )
            page = context.new_page()
            page.goto(uri, wait_until="networkidle")
            page.wait_for_timeout(wait_ms)
            page.close()
            context.close()
            browser.close()

        webms = sorted(video_dir.glob("*.webm"))
        if not webms:
            return {"success": False, "error": "playwright produced no video", "backend": "playwright"}
        webm_to_mp4(webms[-1], mp4_path)
        return {"success": True, "error": None, "backend": "playwright"}


def load_series_palette(series_profile_path: Path) -> dict[str, Any]:
    if not series_profile_path.is_file():
        return {}
    data = json.loads(series_profile_path.read_text(encoding="utf-8"))
    colors = data.get("color_palette") or data.get("palette") or {}
    return {
        "background": colors.get("background") or colors.get("bg"),
        "accent": colors.get("accent") or colors.get("primary"),
        "text": colors.get("text") or colors.get("foreground"),
    }
