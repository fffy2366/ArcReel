"""SessionActor: 每会话一个专属 asyncio task，封装 ClaudeSDKClient 的所有协议调用。

设计：docs/superpowers/specs/2026-04-13-session-actor-design.md

消息泵（2026-08-06 起）：actor 在 connect 后建立**单一持久**的 receive_messages()
迭代器，全生命周期持续消费消息流，而非每个 query 临时开一次 receive_response()。
原因：CLI 会在异步子代理（Task）完成时自行注入 task-notification 并**自主开启新
回合**；若只在 query 期间读流，自治回合的消息会堆积在 SDK 内部缓冲无人消费——
事件日志 / SSE 完全无感知（用户看到"subagent 没有返回内容"），且 idle 清理定时器
会在自治回合进行中途按闲置误杀 CLI 进程，通知就此丢失。
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Literal

from server.agent_runtime.message_serialization import infer_message_type


class _ActorClosed(Exception):
    """Sentinel: actor 已退出（正常或异常），队列中剩余命令以此标记为 error。"""


class _MessageStreamEnded(Exception):
    """SDK 消息流在会话未断开时终结（CLI 进程死亡/被清理），按致命错误处理。"""


def _is_result_message(msg: Any) -> bool:
    """判定回合终结的 result 消息。兼容 SDK Message 对象与测试用的裸 dict。"""
    if isinstance(msg, dict):
        return msg.get("type") == "result"
    return infer_message_type(msg) == "result"


@dataclass
class SessionCommand:
    type: Literal["query", "interrupt", "disconnect"]
    prompt: str | AsyncIterable[dict] | None = None
    session_id: str = "default"
    # query 的 prompt 已被送入 SDK（不代表整轮响应结束）；非 query 命令与 done 同时置位
    sent: asyncio.Event = field(default_factory=asyncio.Event)
    # query 整轮响应完成（以 result 消息为界）；非 query 命令也用它标记处理完毕
    done: asyncio.Event = field(default_factory=asyncio.Event)
    error: BaseException | None = None
    # 仅在 client.query() 正常返回后置真；与 sent 分开，因为失败 complete()
    # 也会唤醒 sent，但那不代表请求已被 SDK 受理。
    accepted: bool = False

    def complete(self, error: BaseException | None = None) -> None:
        """唤醒所有等待者（sent + done）并可选携带 error。

        集中定义避免漏置 sent 或 done 导致调用方挂死——历次 review 发现过
        多个 "只 set done 忘了 set sent" 的回归，此 helper 作为单一契约点。
        """
        if error is not None:
            self.error = error
        self.sent.set()
        self.done.set()


OnMessage = Callable[[dict[str, Any]], None]
ClientFactory = Callable[[], AbstractAsyncContextManager[Any]]


class SessionActor:
    """单 task 拥有一个 ClaudeSDKClient，所有 SDK 操作在同一 async context 中执行。"""

    def __init__(
        self,
        client_factory: ClientFactory,
        on_message: OnMessage,
    ):
        self._client_factory = client_factory
        self._on_message = on_message
        self._cmd_queue: asyncio.Queue[SessionCommand] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._started: asyncio.Event = asyncio.Event()
        self._fatal: BaseException | None = None

    async def start(self) -> None:
        """启动 actor task；等到 connect 成功或 fail-fast 才返回。"""
        assert self._task is None, "SessionActor.start() 不可重入调用"
        self._task = asyncio.create_task(self._run(), name="session-actor")
        started_task = asyncio.create_task(self._started.wait())
        try:
            await asyncio.wait(
                {started_task, self._task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            if not started_task.done():
                started_task.cancel()
        fatal = self._fatal
        if fatal is not None:
            raise fatal

    async def _run(self) -> None:
        try:
            async with self._client_factory() as client:
                self._started.set()
                await self._command_loop(client)
        except BaseException as exc:
            self._fatal = exc
            raise
        finally:
            # 正常 / 异常退出都 drain 残留命令，避免调用方挂死
            self._drain_pending_commands(self._fatal or _ActorClosed())

    async def _start_query(self, client: Any, cmd: SessionCommand) -> SessionCommand:
        """把 query 送入 SDK 并登记为 active；失败时 complete(error) 后抛出（fatal）。"""
        try:
            await client.query(cmd.prompt, session_id=cmd.session_id)
        except BaseException as exc:
            cmd.complete(exc)
            raise
        # prompt 已送入 SDK：释放 HTTP 路径，actor 继续在后台 drain 消息流
        cmd.accepted = True
        cmd.sent.set()
        return cmd

    async def _command_loop(self, client: Any) -> None:
        """统一交织循环：单一持久消息流 + 命令队列。

        消息流生命周期与 client 一致：自治回合（异步子代理完成触发的
        task-notification turn）在 idle 期间产出的消息同样被消费、广播并
        进入事件日志；回合边界以 result 消息判定，而非迭代器终结。
        """
        msg_iter = client.receive_messages().__aiter__()
        msg_task: asyncio.Task | None = asyncio.create_task(msg_iter.__anext__(), name="actor-recv")
        cmd_task: asyncio.Task | None = asyncio.create_task(self._cmd_queue.get(), name="actor-cmd")
        active_query: SessionCommand | None = None
        pending_query: SessionCommand | None = None
        try:
            while True:
                done, _ = await asyncio.wait({msg_task, cmd_task}, return_when=asyncio.FIRST_COMPLETED)

                if msg_task in done:
                    try:
                        msg = msg_task.result()
                    except StopAsyncIteration:
                        # 消息流终结 = CLI 侧连接关闭（进程死亡/被杀）。这不同于
                        # query 回合结束（以 result 消息为界）：流终结后后续 query
                        # 再无响应方，按致命错误收尾让会话进入 error 终态，而不是
                        # 假装闲置等下一条 query 无声失败。
                        stream_end = _MessageStreamEnded("CLI message stream ended unexpectedly")
                        # 与 cmd_task race 到同 tick 的命令已出队，必须显式释放等待者
                        if cmd_task.done():
                            cmd_task.result().complete(stream_end)
                        if active_query is not None:
                            active_query.done.set()
                            active_query = None
                        if pending_query is not None:
                            pending_query.complete(_ActorClosed())
                            pending_query = None
                        raise stream_end
                    msg_task = asyncio.create_task(msg_iter.__anext__(), name="actor-recv")
                    self._on_message(msg)
                    if active_query is not None and _is_result_message(msg):
                        # 回合以 result 为界：完成 active 并按 FIFO 接手 pending
                        finished, active_query = active_query, None
                        finished.done.set()
                        if pending_query is not None:
                            handed_off, pending_query = pending_query, None
                            active_query = await self._start_query(client, handed_off)

                if cmd_task in done:
                    cmd = cmd_task.result()
                    cmd_task = asyncio.create_task(self._cmd_queue.get(), name="actor-cmd")
                    if cmd.type == "disconnect":
                        # 有回合在跑时先 interrupt 让 CLI 的消息流收尾，保持与旧
                        # _drive_query 的 disconnect 语义一致；idle 时不多发。
                        if active_query is not None:
                            await client.interrupt()
                            active_query.done.set()
                            active_query = None
                        if pending_query is not None:
                            pending_query.complete(_ActorClosed())
                            pending_query = None
                        cmd.complete()
                        return  # 触发 __aexit__，同 task disconnect
                    if cmd.type == "interrupt":
                        # 无论 client.interrupt() 成败都要唤醒等待者——常规失败时
                        # 把异常挂到 cmd.error 透传给 send_interrupt；CancelledError 等
                        # 控制流异常不拦截，但 finally 仍保证 cmd 被 complete 避免挂死。
                        caught: Exception | None = None
                        try:
                            await client.interrupt()
                        except Exception as exc:
                            caught = exc
                        finally:
                            cmd.complete(caught)
                        if caught is not None:
                            raise caught
                    elif cmd.type == "query":
                        if active_query is None:
                            active_query = await self._start_query(client, cmd)
                        elif pending_query is None:
                            # 违反 "drain before new query"：暂存，active 回合的
                            # result 到达后按 FIFO 接手执行（与旧语义一致）
                            pending_query = cmd
                        else:
                            # 上层 race 送来第三个 query：拒绝（FIFO 只保留第一个暂存）
                            cmd.complete(RuntimeError("session busy: 当前会话已有待执行 query"))
        finally:
            for task in (msg_task, cmd_task):
                if task is not None and not task.done():
                    task.cancel()
            with contextlib.suppress(Exception):
                await msg_iter.aclose()
            # 异常退出路径：active/pending 已脱离队列，必须显式释放等待者
            if active_query is not None and not active_query.done.is_set():
                active_query.complete(active_query.error or _ActorClosed())
            if pending_query is not None and not pending_query.done.is_set():
                pending_query.complete(pending_query.error or _ActorClosed())

    async def enqueue(self, cmd: SessionCommand) -> None:
        if self._task is not None and self._task.done():
            cmd.complete(self._fatal or _ActorClosed())
            return
        await self._cmd_queue.put(cmd)

    def _drain_pending_commands(self, exc: BaseException) -> None:
        while not self._cmd_queue.empty():
            try:
                cmd = self._cmd_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if not cmd.done.is_set():
                cmd.complete(exc)

    # --- Public accessors (avoid leaking _task to callers) -----------------

    @property
    def task(self) -> asyncio.Task | None:
        """Underlying actor task; None before start()."""
        return self._task

    def add_done_callback(self, callback: Callable[[asyncio.Task], None]) -> None:
        """Register a callback on the actor task. No-op if task not started yet."""
        if self._task is not None:
            self._task.add_done_callback(callback)

    async def wait(self) -> None:
        """Await actor task completion, swallowing any raised exception."""
        if self._task is None:
            return
        with contextlib.suppress(BaseException):
            _ = await self._task  # result intentionally discarded; await 的等待副作用才是意图

    async def cancel_and_wait(self) -> None:
        """Cancel the actor task and wait for it to finish."""
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        with contextlib.suppress(BaseException):
            _ = await self._task  # result intentionally discarded
