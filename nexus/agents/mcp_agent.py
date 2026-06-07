"""
MCPAgent — adapter that launches an external MCP server subprocess and
exposes the same `call_tool()` interface as InProcessAgent.

We manage the subprocess ourselves (via anyio.open_process) rather than
delegating to mcp.client.stdio.stdio_client, because we need direct
access to the process object for SIGSTOP/SIGCONT pause/wake support.
The pump logic mirrors what stdio_client does internally.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import Any

import anyio
import anyio.abc
from mcp import ClientSession, types
from mcp.client.stdio import TextReceiveStream
from mcp.shared.message import SessionMessage

from nexus.agents.manifest import Manifest


class MCPAgent:
    def __init__(
        self,
        manifest: Manifest,
        *,
        aegis=None,
        inbox=None,
    ):
        self._manifest = manifest
        self._aegis = aegis
        self._inbox = inbox
        self._session: ClientSession | None = None
        self._process: anyio.abc.Process | None = None
        self._paused = False
        # asyncio task that owns the task group running the pumps + session
        self._driver_task: asyncio.Task | None = None
        # event that fires once the session is initialised (or failed)
        self._ready_event: asyncio.Event | None = None
        self._start_error: BaseException | None = None
        # signal to tear down the driver task
        self._stop_event: asyncio.Event | None = None

    # ── properties ───────────────────────────────────────────────────────

    @property
    def slug(self) -> str:
        return self._manifest.slug

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ── lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch the subprocess and initialise the MCP client session."""
        if self._session is not None:
            return

        self._ready_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._start_error = None

        # Launch the driver in a background asyncio task.
        # anyio.create_task_group() needs to run inside an anyio event loop
        # which is compatible with asyncio (pytest-asyncio uses asyncio).
        loop = asyncio.get_event_loop()
        self._driver_task = loop.create_task(self._run_driver())

        # Wait until session is ready (or failed)
        await self._ready_event.wait()
        if self._start_error is not None:
            raise self._start_error

    async def _run_driver(self) -> None:
        """
        Owns the full lifetime of the subprocess + MCP session.

        Runs inside an asyncio Task so the caller (start()) can await
        _ready_event without blocking.  Terminates when _stop_event fires.
        """
        rc = self._manifest.runtime
        env = {
            **os.environ,
            **{k: os.environ[k] for k in rc.env_keys if k in os.environ},
        }

        try:
            # Open subprocess via anyio so we get a proper Process object
            # with a .pid attribute (anyio wraps asyncio.subprocess.Process).
            self._process = await anyio.open_process(
                [rc.command, *rc.args],
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=sys.stderr,
                env=env,
            )
        except Exception as exc:
            self._start_error = exc
            self._ready_event.set()
            return

        # Create the memory stream pairs that ClientSession expects.
        # Buffer size 0 matches what stdio_client uses.
        read_send, read_recv = anyio.create_memory_object_stream[SessionMessage | Exception](0)
        write_send, write_recv = anyio.create_memory_object_stream[SessionMessage](0)

        async def _stdout_reader() -> None:
            """Pump subprocess stdout → read_send (for ClientSession to consume)."""
            assert self._process.stdout is not None
            try:
                async with read_send:
                    buffer = ""
                    async for chunk in TextReceiveStream(self._process.stdout):
                        lines = (buffer + chunk).split("\n")
                        buffer = lines.pop()
                        for line in lines:
                            if not line.strip():
                                continue
                            try:
                                msg = types.JSONRPCMessage.model_validate_json(line)
                            except Exception as exc:
                                await read_send.send(exc)
                                continue
                            await read_send.send(SessionMessage(msg))
            except anyio.ClosedResourceError:
                await anyio.lowlevel.checkpoint()

        async def _stdin_writer() -> None:
            """Pump write_recv (ClientSession output) → subprocess stdin."""
            assert self._process.stdin is not None
            try:
                async with write_recv:
                    async for session_msg in write_recv:
                        payload = (
                            session_msg.message.model_dump_json(
                                by_alias=True, exclude_none=True
                            )
                            + "\n"
                        ).encode()
                        await self._process.stdin.send(payload)
            except anyio.ClosedResourceError:
                await anyio.lowlevel.checkpoint()

        async def _session_runner() -> None:
            """Initialise the ClientSession, signal ready, then wait for stop."""
            async with ClientSession(read_recv, write_send) as session:
                self._session = session
                try:
                    await session.initialize()
                    self._ready_event.set()
                    # Keep the session alive until stop() is called
                    await self._stop_event.wait()
                except Exception as exc:
                    self._start_error = exc
                    self._ready_event.set()
                finally:
                    self._session = None

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(_stdout_reader)
                tg.start_soon(_stdin_writer)
                tg.start_soon(_session_runner)
        except Exception:
            pass
        finally:
            # Ensure the ready event is always set so start() doesn't hang
            if not self._ready_event.is_set():
                self._ready_event.set()
            await self._terminate_process()

    async def stop(self) -> None:
        """Signal the driver task to shut down and wait for it."""
        if self._stop_event is not None:
            self._stop_event.set()

        if self._driver_task is not None and not self._driver_task.done():
            # Give the task a moment to exit cleanly; cancel if it lingers
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._driver_task), timeout=3.0
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._driver_task.cancel()
                try:
                    await self._driver_task
                except (asyncio.CancelledError, Exception):
                    pass

        self._driver_task = None
        self._session = None

        # Belt-and-suspenders: make sure the process is really gone
        if self._process is not None and self._process.returncode is None:
            await self._terminate_process()

    async def _terminate_process(self) -> None:
        """Best-effort termination of the subprocess."""
        proc = self._process
        if proc is None:
            return
        self._process = None
        if proc.returncode is not None:
            return
        try:
            proc.terminate()
            try:
                with anyio.fail_after(2.0):
                    await proc.wait()
            except TimeoutError:
                proc.kill()
                await proc.wait()
        except (ProcessLookupError, OSError):
            pass

    # ── pause / wake ─────────────────────────────────────────────────────

    def pause(self) -> None:
        """Freeze the subprocess with SIGSTOP and mark it paused."""
        self._paused = True
        pid = self.pid
        if pid is not None:
            try:
                os.kill(pid, signal.SIGSTOP)
            except (ProcessLookupError, PermissionError):
                pass

    def wake(self) -> None:
        """Resume the subprocess with SIGCONT and clear the paused flag."""
        pid = self.pid
        if pid is not None:
            try:
                os.kill(pid, signal.SIGCONT)
            except (ProcessLookupError, PermissionError):
                pass
        self._paused = False

    # ── tool call ────────────────────────────────────────────────────────

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        if self._paused:
            raise RuntimeError(
                f"agent {self.slug!r} is paused; wake before calling"
            )
        if self._session is None:
            raise RuntimeError(
                f"agent {self.slug!r} is not started; call start() first"
            )
        from nexus.agents._gating import gate_tool_call
        await gate_tool_call(
            self.slug, self._manifest, tool_name, args, self._aegis, self._inbox,
        )
        return await self._session.call_tool(tool_name, arguments=args)
