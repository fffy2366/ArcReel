from server.services.director_script_export import build_director_storyboard_episode_script


def test_director_storyboard_export_uses_canonical_generated_assets_schema():
    script = build_director_storyboard_episode_script(
        project={"title": "测试项目", "episodes": [{"episode": 1, "title": "第一集"}]},
        episode=1,
        video_prompts={
            "videos": [
                {
                    "video_id": "VID-E1S01",
                    "shot_id": "E1S01",
                    "keyframe_id": "KF-E1S01-guide",
                    "title": "开场",
                    "duration_seconds": 5,
                    "prompt": "角色推门进入房间，镜头轻微推进。",
                }
            ]
        },
        director_shots={
            "shot_groups": [
                {
                    "shots": [
                        {
                            "shot_id": "E1S01",
                            "source_excerpt": "他推门进入房间。",
                            "duration_seconds": 5,
                            "shot_size": "中景",
                            "camera_movement": "轻微推进",
                            "screen_subject": "角色站在门口",
                            "action": "推门进入房间",
                            "performance": "谨慎",
                            "lighting": "室内暖光",
                        }
                    ]
                }
            ]
        },
    )

    assets = script["segments"][0]["generated_assets"]
    assert "last_generation_inputs" not in assets
    assert "qa_report" not in assets
    assert assets["status"] == "pending"
