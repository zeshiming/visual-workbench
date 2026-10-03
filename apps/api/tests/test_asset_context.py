from src.routers.assets import AssetContextRequest


def test_asset_context_request_supports_feedback_selection() -> None:
    request = AssetContextRequest(feedbackId="3405", referenceAssetId="reference-1")

    assert request.assetIds == []
    assert request.feedbackId == "3405"
    assert request.referenceAssetId == "reference-1"
