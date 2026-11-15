import sys
from types import SimpleNamespace

from fazenda_cv.detection import YoloXOnnxDetector


def test_configures_cpu_session_threads(tmp_path, monkeypatch):
    captured = {}

    def session(path, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(get_inputs=lambda: [SimpleNamespace(name="image")])

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(SessionOptions=SimpleNamespace, InferenceSession=session),
    )
    weights = tmp_path / "model.onnx"
    weights.write_bytes(b"test")
    YoloXOnnxDetector(str(weights), cpu_threads=4)
    assert captured["sess_options"].intra_op_num_threads == 4
    assert captured["sess_options"].inter_op_num_threads == 1
    assert captured["providers"] == ["CPUExecutionProvider"]
