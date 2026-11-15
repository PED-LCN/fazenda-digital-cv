from copy import deepcopy

import pytest

from fazenda_cv.passage_totals import PassageTotals


def event(identity="a", access="curral", session="s1", direction="in", source="cam1"):
    return dict(
        schema_version=2,
        event_type="passage",
        event_id=identity,
        access_id=access,
        session_id=session,
        source_id=source,
        data={"direction": direction},
    )


def test_totals_separate_access_session_and_source_and_ignore_retries():
    totals = PassageTotals()
    for item in [
        event(),
        event(),
        event("b", direction="out"),
        event("c", access="ordenha"),
        event("d", session="s2"),
        event("e", source="cam2"),
    ]:
        totals.record(item)
    rows = totals.rows()
    assert len(rows) == 4
    assert rows[0] == dict(
        source_id="cam1", session_id="s1", access_id="curral", **{"in": 1, "out": 1}
    )
    assert sum(row["in"] for row in rows) == 4
    assert PassageTotals().rows() == []


def test_conflicting_retry_is_rejected_without_changing_count():
    totals = PassageTotals()
    original = event()
    totals.record(original)
    changed = deepcopy(original)
    changed["data"]["direction"] = "out"
    with pytest.raises(ValueError, match="diferente"):
        totals.record(changed)
    assert totals.rows()[0]["in"] == 1
    assert totals.rows()[0]["out"] == 0


@pytest.mark.parametrize(
    "change", [{"session_id": ""}, {"schema_version": 1}, {"data": {"direction": "unknown"}}]
)
def test_invalid_event_does_not_change_totals(change):
    totals = PassageTotals()
    payload = event()
    payload.update(change)
    with pytest.raises(ValueError):
        totals.record(payload)
    assert totals.rows() == []


def test_cli_queries_persisted_cv_outbox(tmp_path, monkeypatch, capsys):
    import json

    from fazenda_cv.passage_totals import main
    from fazenda_cv.webhook import EventOutbox

    path = tmp_path / "outbox.sqlite3"
    queue = EventOutbox(path)
    queue.enqueue(event())
    monkeypatch.setattr("sys.argv", ["totals", "--outbox", str(path)])
    main()
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["in"] == 1
    assert rows[0]["access_id"] == "curral"
