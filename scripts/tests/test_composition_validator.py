import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composition_validator import validate_production


def test_validate_flags_missing_video(tmp_path):
    storyboard = {
        "scenes": [
            {
                "scene_id": "SC01",
                "shots": [{"shot": 1, "type": "WIDE", "duration_seconds": 5}],
            }
        ]
    }
    (tmp_path / "cinematic_videos" / "SC01").mkdir(parents=True)
    report = validate_production(storyboard=storyboard, assets_root=tmp_path)
    assert report["passed"] is False
    assert report["error_count"] >= 1


if __name__ == "__main__":
    test_validate_flags_missing_video()
    print("test_composition_validator: ok")
