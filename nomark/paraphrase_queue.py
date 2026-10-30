"""Single-replica admission for NMT; tickets carry no text."""
import secrets
import time
from contextlib import contextmanager

from nomark.jobs import JobError


class ParaphraseQueue:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.tickets = {}
        self.running = None
        self.task = None
        self.blocked = False

    def sweep(self):
        now = self.clock()
        self.tickets = {key: value for key, value in self.tickets.items() if value['expires'] > now}
        if self.running is None and not any(t['state'] == 'ready' for t in self.tickets.values()):
            for ticket in self.tickets.values():
                ticket.update(state='ready', expires=now + 20)
                break

    def reserve(self, owner):
        if self.blocked:
            raise JobError('paraphrase_unavailable', 503)
        self.sweep()
        if (self.running and self.running[1] == owner) or any(t['owner'] == owner for t in self.tickets.values()):
            raise JobError('paraphrase_ticket_exists', 409)
        if sum(t['state'] == 'waiting' for t in self.tickets.values()) >= 2:
            raise JobError('queue_full', 503)
        token = secrets.token_urlsafe(32)
        self.tickets[token] = {'owner': owner, 'state': 'waiting', 'expires': self.clock() + 180}
        return {'token': token, **self.status(token, owner)}

    def status(self, token, owner):
        self.sweep()
        item = self.tickets.get(token)
        if not item or item['owner'] != owner:
            raise JobError('queue_expired', 410)
        waiting = [key for key, value in self.tickets.items() if value['state'] == 'waiting']
        return {'ok': True, 'state': item['state'], 'position': waiting.index(token) + 1 if token in waiting else 0}

    def cancel(self, token, owner):
        if self.running == (token, owner):
            if self.task:
                self.task.cancel()
        else:
            self.status(token, owner)
            self.tickets.pop(token, None)
        self.sweep()

    @contextmanager
    def claim(self, token, owner):
        if self.blocked:
            raise JobError('paraphrase_unavailable', 503)
        if self.status(token, owner)['state'] != 'ready' or self.running is not None:
            raise JobError('queue_not_ready', 409)
        del self.tickets[token]
        self.running = (token, owner)
        try:
            yield
        finally:
            self.running = self.task = None
            self.sweep()
