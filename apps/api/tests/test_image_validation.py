from src.services.image_validation import validate_image_result


PIXEL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC"


def test_image_validation_accepts_valid_same_size_image() -> None:
    report = validate_image_result(PIXEL, PIXEL)
    assert report.ok is True
    assert report.metrics["sourceWidth"] == 2
    assert report.metrics["outputWidth"] == 2


def test_image_validation_rejects_invalid_image() -> None:
    report = validate_image_result(PIXEL, "data:image/png;base64,invalid")
    assert report.ok is False


def test_raw_image_validation_can_record_provider_size_without_accepting_it_as_final() -> None:
    from PIL import Image
    import io
    import base64

    output = io.BytesIO()
    Image.new('RGB', (3, 2), (120, 120, 120)).save(output, format='PNG')
    raw = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
    report = validate_image_result(PIXEL, raw, require_same_size=False)
    assert report.ok is True
    assert report.metrics['outputWidth'] == 3
    assert report.metrics['outputHeight'] == 2

    final_report = validate_image_result(PIXEL, raw)
    assert final_report.ok is False
    assert final_report.issues
