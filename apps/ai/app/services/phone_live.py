"""
What the audience sees during a real phone call: every event of the call (status, what the caller says, what the agent says,
each tool it runs) published to the web app's « Appel en cours » panel over Server-Sent Events (GET /phone/live).

Read-only and in memory: the events of the last calls are kept so a page opened in the middle of a call catches up.
"""

import asyncio
import json
import time
from collections import OrderedDict
from collections.abc import AsyncIterator

MAX_EVENTS = 600  # per call
MAX_CALLS = 10


class LiveBus:
    def __init__(self) -> None:
        self.events: OrderedDict[str, list[dict]] = OrderedDict()  # call id → its events, oldest call first
        self.subscribers: set[asyncio.Queue[dict]] = set()

    def publish(self, call_id: str, event: dict) -> dict:
        ev = {"callId": call_id, "at": round(time.time(), 3), **event}
        log = self.events.setdefault(call_id, [])
        self.events.move_to_end(call_id)
        log.append(ev)
        del log[:-MAX_EVENTS]
        while len(self.events) > MAX_CALLS:
            self.events.popitem(last=False)
        for q in list(self.subscribers):
            if q.qsize() < 2000:  # a stuck reader never blocks the call
                q.put_nowait(ev)
        return ev

    def latest(self) -> list[dict]:
        """The events of the most recent call (to catch up)."""
        return list(next(reversed(self.events.values()), []))

    async def stream(self, ping_s: float = 15) -> AsyncIterator[str]:
        """SSE frames: the latest call's events first, then live events; a comment line every `ping_s` keeps proxies open."""
        q: asyncio.Queue[dict] = asyncio.Queue()
        self.subscribers.add(q)
        try:
            for ev in self.latest():
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            yield ": ready\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), ping_s)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            self.subscribers.discard(q)


live = LiveBus()
