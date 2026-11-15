import cv2
import numpy as np

from fazenda_cv.__main__ import _output_fps
from fazenda_cv.sources import OpenCVSource


def test_file_timeline_is_stable_across_replays(tmp_path):
    video = tmp_path / "recording.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()

    first_source = OpenCVSource(str(video))
    first = list(first_source.frames())
    second = list(OpenCVSource(str(video)).frames())

    assert first_source.fps == 10
    assert [frame.video_offset_ms for frame in first] == [0, 100, 200]
    assert [frame.video_offset_ms for frame in second] == [0, 100, 200]
    assert len({frame.session_id for frame in first}) == 1
    assert first[0].session_id != second[0].session_id
    assert all(frame.time_basis == "replay" for frame in first)


def test_output_fps_falls_back_without_file_metadata():
    source = OpenCVSource("recording.avi")
    assert _output_fps(source, 30) == 30
    source.fps = 10.0
    assert _output_fps(source, 30) == 10.0


def test_selected_segment_preserves_original_offsets_and_output_speed(tmp_path):
    video = tmp_path / "segment.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(30):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()
    source = OpenCVSource(str(video), start_seconds=1, duration_seconds=1, frame_step=2)
    frames = list(source.frames())
    assert [f.video_offset_ms for f in frames] == [1000, 1200, 1400, 1600, 1800]
    assert _output_fps(source, 30) == 5


def test_rtsp_rejects_file_sampling():
    import pytest

    with pytest.raises(ValueError, match="arquivo"):
        OpenCVSource("rtsp://example.test/camera", frame_step=2)


def test_invalid_segment_parameters():
    import pytest

    for kwargs in (
        {"start_seconds": -1},
        {"start_seconds": float("nan")},
        {"duration_seconds": 0},
        {"duration_seconds": float("inf")},
        {"frame_step": 0},
    ):
        with pytest.raises(ValueError):
            OpenCVSource("video.avi", **kwargs)


def test_outbox_requires_access_id(capsys):
    import pytest

    from fazenda_cv.__main__ import main

    with pytest.raises(SystemExit):
        main(["--source", "video.avi", "--simulator", "--outbox", "queue.sqlite3"])
    assert "access-id" in capsys.readouterr().err
