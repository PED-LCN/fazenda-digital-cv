import pytest

from fazenda_cv.mot_boxes import read_mot_boxes


def test_reads_real_format_with_explicit_scale_and_empty_frame():
    frames = read_mot_boxes(
        ["1,3,528,328,146,82,1,-1,-1,-1\n", "2,3,528,328,146,82,0,-1,-1,-1\n"],
        coordinate_scale=2,
        first_frame=1,
        last_frame=3,
    )
    assert frames[1][0].xyxy == (1056, 656, 1348, 820)
    assert 2 not in frames


@pytest.mark.parametrize("scale", [0, -1, float("nan")])
def test_rejects_invalid_scale(scale):
    with pytest.raises(ValueError, match="coordinate_scale"):
        read_mot_boxes([], coordinate_scale=scale)


def test_rejects_duplicate_or_invalid_rows():
    row = "1,3,528,328,146,82,1\n"
    with pytest.raises(ValueError, match="duplicado"):
        read_mot_boxes([row, row])
    with pytest.raises(ValueError, match="inválida"):
        read_mot_boxes(["1,3,-1,0,10,10,1\n"])
