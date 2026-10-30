from __future__ import annotations

from contextlib import contextmanager
import math
import secrets
import time

from nomark.jobs import JobError


class Admission:
    """Reserve processing capacity before any file body is accepted."""

    def __init__(self, capacity=2, max_waiting=8, clock=time.monotonic):
        self.capacity = capacity
        self.max_waiting = max_waiting
        self.clock = clock
        self.active = 0
        self.tickets = {}

    def sweep(self):
        now = self.clock()
        for token in list(self.tickets):
            if self.tickets[token]["expires"] <= now:
                del self.tickets[token]
        ready = sum(item["state"] == "ready" for item in self.tickets.values())
        for ticket in self.tickets.values():
            if self.active + ready >= self.capacity:
                break
            if ticket["state"] == "waiting":
                ticket.update(state="ready", expires=now + 20)
                ready += 1

    def reserve(self):
        self.sweep()
        waiting = sum(item["state"] == "waiting" for item in self.tickets.values())
        if waiting >= self.max_waiting:
            raise JobError("queue_full", 503)
        token = secrets.token_urlsafe(32)
        self.tickets[token] = {"state": "waiting", "expires": self.clock() + 120}
        return {"token": token, **self.status(token)}

    def status(self, token):
        self.sweep()
        if token not in self.tickets:
            raise JobError("queue_expired", 410)
        item = self.tickets[token]
        pending = [key for key, value in self.tickets.items() if value["state"] == "waiting"]
        return {"ok": True, "state": item["state"], "position": pending.index(token) + 1 if item["state"] == "waiting" else 0, "expires_in": max(1, math.ceil(item["expires"] - self.clock()))}

    def cancel(self, token):
        self.tickets.pop(token, None)
        self.sweep()

    @contextmanager
    def claim(self, token=None):
        self.sweep()
        if token:
            item = self.status(token)
            if item["state"] != "ready":
                raise JobError("queue_not_ready", 409)
            del self.tickets[token]
        elif self.active + len(self.tickets) >= self.capacity:
            raise JobError("server_busy", 503)
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1
            self.sweep()
