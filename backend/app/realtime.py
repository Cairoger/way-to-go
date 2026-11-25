import asyncio
from collections import defaultdict
from dataclasses import dataclass, field

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from .core import COOKIE, make_session, public_origin, valid_session


@dataclass(eq=False)
class Connection:
    user_id: str
    session_id: str
    updates: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=32))
    loop: asyncio.AbstractEventLoop = field(default_factory=asyncio.get_running_loop)

    def notify(self, event: dict):
        if self.updates.full():
            # Clients refetch after each invalidation. Coalesce a slow client's backlog.
            while not self.updates.empty():
                self.updates.get_nowait()
            self.updates.put_nowait({"type": "resync"})
        self.updates.put_nowait(event)


class Hub:
    def __init__(self):
        self.connections: dict[str, set[Connection]] = defaultdict(set)

    async def publish(self, trip_id: str, event: dict):
        for connection in tuple(self.connections.get(trip_id, ())):
            connection.loop.call_soon_threadsafe(connection.notify, event)

    async def presence(self, trip_id: str):
        members = sorted({connection.user_id for connection in self.connections.get(trip_id, ())})
        await self.publish(trip_id, {"type": "presence", "members": members})

    async def publish_to(self, trip_id: str, user_id: str, event: dict):
        for connection in tuple(self.connections.get(trip_id, ())):
            if connection.user_id == user_id:
                connection.loop.call_soon_threadsafe(connection.notify, event)

    def revalidate(self, session_id: str):
        for group in tuple(self.connections.values()):
            for connection in tuple(group):
                if connection.session_id == session_id:
                    connection.loop.call_soon_threadsafe(connection.notify, {"type": "resync"})


hub = Hub()
router = APIRouter()


def identify(token: str | None, trip_id: str):
    with make_session() as db:
        login = valid_session(db, token, trip_id=trip_id)
        if not login:
            return None
        return login.user_id, login.id


@router.websocket("/ws/trips/{trip_id}")
async def subscribe(socket: WebSocket, trip_id: str):
    if socket.headers.get("origin") != public_origin():
        await socket.close(code=4403)
        return
    token = socket.cookies.get(COOKIE)
    identity = await run_in_threadpool(identify, token, trip_id)
    if not identity:
        await socket.close(code=4403)
        return
    await socket.accept()
    connection = Connection(*identity)
    hub.connections[trip_id].add(connection)
    await hub.presence(trip_id)

    async def send_updates():
        while True:
            try:
                event = await asyncio.wait_for(connection.updates.get(), timeout=15)
            except TimeoutError:
                event = {"type": "heartbeat"}
            if not await run_in_threadpool(identify, token, trip_id):
                await socket.close(code=4403)
                return
            await asyncio.wait_for(socket.send_json(event), timeout=10)

    async def receive():
        while True:
            message = await socket.receive()
            if message["type"] == "websocket.disconnect":
                return
            # The server only accepts a heartbeat. Edits go through the REST API.
            if message.get("text") != "ping":
                await socket.close(code=1008)
                return
            if not await run_in_threadpool(identify, token, trip_id):
                await socket.close(code=4403)
                return

    async def until_closed(run, group):
        try:
            await run()
        except (TimeoutError, WebSocketDisconnect, OSError):
            pass
        finally:
            group.cancel_scope.cancel()

    try:
        async with anyio.create_task_group() as workers:
            workers.start_soon(until_closed, send_updates, workers)
            workers.start_soon(until_closed, receive, workers)
    finally:
        group = hub.connections.get(trip_id)
        if group is not None:
            group.discard(connection)
            if group:
                await hub.presence(trip_id)
            else:
                hub.connections.pop(trip_id, None)
