from pathlib import Path

from src.skills.registry import SkillRegistry


def test_skill_context_is_bounded_and_non_executable(tmp_path: Path) -> None:
    directory = tmp_path / 'portrait'
    directory.mkdir()
    (directory / 'manifest.json').write_text(
        '{"id":"portrait","name":"Portrait","version":"2","description":"自然人像","tools":["apply_adjustments"]}',
    )
    (directory / 'skill.md').write_text('保持身份，优先使用保守局部处理。')
    registry = SkillRegistry()
    assert registry.load_directory(tmp_path) == 1
    context = registry.planner_context()
    assert 'portrait@2' in context
    assert 'apply_adjustments' in context
    assert '执行任意' not in context
    assert len(context) <= 8_000
