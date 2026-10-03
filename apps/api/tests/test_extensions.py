from pathlib import Path

from src.mcp.client import McpClientError, get_mcp_client
from src.mcp.registry import McpServerConfig, mcp_server_registry
from src.skills.registry import SkillManifest, SkillRegistry, skill_registry


def test_skill_loader_reads_manifest_and_instructions(tmp_path: Path) -> None:
    skill_dir = tmp_path / "portrait"
    skill_dir.mkdir()
    (skill_dir / "manifest.json").write_text(
        '{"id":"portrait","name":"Portrait","description":"test","tools":["apply_ai_edit"]}',
        encoding="utf-8",
    )
    (skill_dir / "skill.md").write_text("保持人物身份。", encoding="utf-8")

    registry = SkillRegistry()
    assert registry.load_directory(tmp_path) == 1
    assert registry.get("portrait") is not None
    assert registry.get("portrait").instructions == "保持人物身份。"


def test_disabled_mcp_server_cannot_create_client() -> None:
    mcp_server_registry.register(McpServerConfig(id="disabled-test", name="Test", transport="http", url="https://example.com"))
    try:
        get_mcp_client("disabled-test")
    except McpClientError as exc:
        assert "disabled" in str(exc).lower()
    else:
        raise AssertionError("disabled MCP server should not create a client")


def test_mcp_secret_ref_is_metadata_only() -> None:
    server = McpServerConfig(
        id='secret-ref', name='Secret Ref', transport='http', url='https://example.com',
        enabled=True, secret_ref='photo.api',
    )
    assert server.secret_ref == 'photo.api'
    assert 'actual-secret' not in server.model_dump_json()
    try:
        McpServerConfig(
            id='bad-secret-ref', name='Bad', transport='http', url='https://example.com',
            secret_ref='../../secret',
        )
    except ValueError as exc:
        assert 'secret_ref' in str(exc)
    else:
        raise AssertionError('unsafe secret_ref should be rejected')


def test_extension_boundaries_reject_unsafe_configuration(tmp_path: Path) -> None:
    try:
        McpServerConfig(id="stdio", name="stdio", transport="stdio", enabled=True)
    except ValueError as exc:
        assert "no-sandbox" in str(exc)
    else:
        raise AssertionError("enabled stdio MCP must be rejected without a sandbox")

    skill_dir = tmp_path / "oversized"
    skill_dir.mkdir()
    (skill_dir / "manifest.json").write_text('{"id":"oversized","name":"Oversized"}', encoding="utf-8")
    (skill_dir / "skill.md").write_text("x" * 64_001, encoding="utf-8")
    registry = SkillRegistry()
    assert registry.load_directory(tmp_path) == 0


def test_extension_registries_can_add_disable_and_remove_without_execution():
    server = McpServerConfig(id='managed-test', name='Managed', transport='http', url='https://example.com')
    mcp_server_registry.register(server)
    assert mcp_server_registry.get('managed-test').enabled is False
    enabled = mcp_server_registry.set_enabled('managed-test', True)
    assert enabled.enabled is True
    disabled = mcp_server_registry.set_enabled('managed-test', False)
    assert disabled.enabled is False
    assert mcp_server_registry.remove('managed-test') is True

    skill_registry.register(SkillManifest(id='managed-skill', name='Managed Skill', tools=[], enabled=False))
    assert skill_registry.get('managed-skill').enabled is False
    assert skill_registry.set_enabled('managed-skill', True).enabled is True
    assert skill_registry.remove('managed-skill') is True
