from src.services.image_utils import apply_editor_region_mask
from src.services.image_validation import validate_image_result


PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsSHBgYGBgYgADAA3qASRmXGo7AAAAAElFTkSuQmCC'


def test_editor_region_mask_preserves_dimensions():
    result = apply_editor_region_mask(PIXEL, PIXEL, [{'center_x': 0.5, 'center_y': 0.5, 'radius': 1}])
    report = validate_image_result(PIXEL, result)
    assert report.ok


def test_editor_region_mask_requires_valid_region():
    try:
        apply_editor_region_mask(PIXEL, PIXEL, [])
    except ValueError as exc:
        assert '区域' in str(exc)
    else:
        raise AssertionError('missing editor region should fail')
