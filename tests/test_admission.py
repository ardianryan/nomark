import pytest

from nomark.admission import Admission
from nomark.jobs import JobError


def test_fifo_and_capacity_reservations():
    queue = Admission(capacity=2)
    first, second, third = [queue.reserve() for _ in range(3)]
    assert first["state"] == second["state"] == "ready"
    assert third["state"] == "waiting"
    assert third["position"] == 1
    with queue.claim(first["token"]):
        assert queue.active == 1
        assert queue.status(third["token"])["state"] == "waiting"
        with pytest.raises(JobError):
            with queue.claim():
                pass
    assert queue.status(third["token"])["state"] == "ready"
    assert queue.active == 0


def test_queue_bounds_expiry_and_cancellation():
    now = [0]
    queue = Admission(capacity=1, max_waiting=2, clock=lambda: now[0])
    first, second, third = [queue.reserve() for _ in range(3)]
    with pytest.raises(JobError) as failure:
        queue.reserve()
    assert failure.value.code == "queue_full"
    now[0] = 21
    assert queue.status(second["token"])["state"] == "ready"
    with pytest.raises(JobError):
        queue.status(first["token"])
    queue.cancel(second["token"])
    assert queue.status(third["token"])["state"] == "ready"
    now[0] = 200
    queue.sweep()
    assert queue.tickets == {}


def test_cannot_claim_waiting_or_unrelated_ticket():
    queue = Admission(capacity=1)
    first, second = queue.reserve(), queue.reserve()
    with pytest.raises(JobError) as failure:
        with queue.claim(second["token"]):
            pass
    assert failure.value.code == "queue_not_ready"
    with pytest.raises(JobError):
        with queue.claim("unrelated"):
            pass
    queue.cancel(first["token"])
    with queue.claim(second["token"]):
        assert queue.active == 1
    assert queue.active == 0
