from hpctel.validation import validate_batch

_NOW_NS = 1_800_000_000_000_000_000  # an arbitrary fixed "now" for determinism


def test_accepts_well_formed_batch():
    samples = [("node-1", 1, _NOW_NS, 42, 12.5)]
    result = validate_batch(1, "test-agent", samples, now_ns=_NOW_NS)
    assert result.batch_rejected_reason_code is None
    assert len(result.accepted) == 1
    assert result.accepted[0].node_id == "node-1"
    assert result.dropped_reason_codes == []


def test_rejects_unsupported_schema_version():
    samples = [("node-1", 1, _NOW_NS, 42, 12.5)]
    result = validate_batch(999, "test-agent", samples, now_ns=_NOW_NS)
    assert result.batch_rejected_reason_code == "schema_mismatch"
    assert result.accepted == []


def test_drops_sample_with_unknown_metric_id_but_keeps_rest_of_batch():
    samples = [
        ("node-1", 1, _NOW_NS, 42, 12.5),  # known metric_id
        ("node-1", 9999, _NOW_NS, 42, 1.0),  # unknown metric_id
    ]
    result = validate_batch(1, "test-agent", samples, now_ns=_NOW_NS)
    assert result.batch_rejected_reason_code is None
    assert len(result.accepted) == 1
    assert result.accepted[0].metric_id == 1
    assert result.dropped_reason_codes == ["unknown_metric_id"]


def test_drops_sample_with_negative_timestamp():
    samples = [("node-1", 1, -5, 42, 12.5)]
    result = validate_batch(1, "test-agent", samples, now_ns=_NOW_NS)
    assert result.accepted == []
    assert result.dropped_reason_codes == ["invalid_timestamp"]


def test_drops_sample_more_than_24h_in_future():
    far_future = _NOW_NS + 25 * 60 * 60 * 1_000_000_000
    samples = [("node-1", 1, far_future, 42, 12.5)]
    result = validate_batch(1, "test-agent", samples, now_ns=_NOW_NS)
    assert result.accepted == []
    assert result.dropped_reason_codes == ["invalid_timestamp"]


def test_accepts_sample_within_last_minute_as_negative_control():
    recent = _NOW_NS - 60 * 1_000_000_000
    samples = [("node-1", 1, recent, 42, 12.5)]
    result = validate_batch(1, "test-agent", samples, now_ns=_NOW_NS)
    assert len(result.accepted) == 1
    assert result.dropped_reason_codes == []


def test_batch_with_only_known_metric_ids_is_fully_accepted():
    samples = [("node-1", metric_id, _NOW_NS, 0, 1.0) for metric_id in range(1, 11)]
    result = validate_batch(1, "test-agent", samples, now_ns=_NOW_NS)
    assert len(result.accepted) == 10
    assert result.dropped_reason_codes == []
