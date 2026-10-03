from src.models.schemas import AgentRunRequest


def test_agent_run_request_defaults_to_unapproved() -> None:
    request = AgentRunRequest(
        config={
            "analysis": {"host": "https://example.com/v1", "key": "", "model": "analysis"},
            "edit": {"host": "https://example.com/v1", "key": "", "model": "edit"},
        },
        content={"image": "data:image/png;base64,abc", "content": "edit"},
    )
    assert request.approved is False
    assert request.plan is None
