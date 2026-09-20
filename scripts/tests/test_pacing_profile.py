import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pacing_profile import apply_pacing_to_storyboard, build_pacing_profile


def test_build_pacing_profile_basic():
    scenes = [
        {"start_seconds": 0, "end_seconds": 3, "duration_seconds": 3},
        {"start_seconds": 3, "end_seconds": 8, "duration_seconds": 5},
    ]
    profile = build_pacing_profile(source="test.mp4", duration_seconds=8, scenes=scenes)
    assert profile["scene_count"] == 2
    assert profile["median_shot_seconds"] == 4.0
    assert "recommended" in profile


def test_apply_pacing_clamps_shots():
    storyboard = {
        "scenes": [
            {
                "scene_id": "SC01",
                "duration_seconds": 20,
                "shots": [
                    {"shot": 1, "duration_seconds": 10},
                    {"shot": 2, "duration_seconds": 10},
                ],
            }
        ]
    }
    profile = {
        "hook_window_seconds": 30,
        "recommended": {
            "default_shot_seconds": 5,
            "min_shot_seconds": 3,
            "max_shot_seconds": 8,
            "hook_shot_seconds": 4,
        },
    }
    updated, changes = apply_pacing_to_storyboard(storyboard, profile)
    assert updated["scenes"][0]["shots"][0]["duration_seconds"] <= 8
    assert len(changes) >= 1


if __name__ == "__main__":
    test_build_pacing_profile_basic()
    test_apply_pacing_clamps_shots()
    print("test_pacing_profile: ok")
