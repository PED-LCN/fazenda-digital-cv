import cv2
import numpy as np

from fazenda_cv.sources import OpenCVSource


def test_file_timeline_is_stable_across_replays(tmp_path):
    video = tmp_path / "recording.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()

    first = list(OpenCVSource(str(video)).frames())
    second = list(OpenCVSource(str(video)).frames())

    assert [frame.video_offset_ms for frame in first] == [0, 100, 200]
    assert [frame.video_offset_ms for frame in second] == [0, 100, 200]
    assert len({frame.session_id for frame in first}) == 1
    assert first[0].session_id != second[0].session_id
    assert all(frame.time_basis == "replay" for frame in first)
