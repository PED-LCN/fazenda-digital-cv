import cv2
import numpy as np
import pytest

from fazenda_cv.presentation_video import export_presentation


@pytest.mark.parametrize("fps", [30, 60])
@pytest.mark.parametrize("interpolation", ["motion", "blend"])
def test_interpolated_copy_preserves_duration_and_original(tmp_path, fps, interpolation):
    source = tmp_path / "original.avi"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 5, (96, 64))
    assert writer.isOpened()
    for i in range(10):
        frame = np.zeros((64, 96, 3), dtype=np.uint8)
        cv2.rectangle(frame, (i * 3, 15), (i * 3 + 15, 30), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    original = source.read_bytes()
    target = tmp_path / "presentation.mp4"
    export_presentation(source, target, fps=fps, width=96, interpolation=interpolation)
    capture = cv2.VideoCapture(str(target))
    assert capture.isOpened()
    assert capture.get(cv2.CAP_PROP_FPS) == pytest.approx(fps)
    assert capture.get(cv2.CAP_PROP_FRAME_COUNT) == 2 * fps
    capture.release()
    assert source.read_bytes() == original
    with pytest.raises(ValueError):
        export_presentation(source, target)
