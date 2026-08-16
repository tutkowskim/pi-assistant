import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings

MEMORY_LIMIT = "128m"
CPU_LIMIT = "0.5"
PIDS_LIMIT = "64"
TMPFS_LIMIT = "16m"
NOFILE_LIMIT = "64:64"


@dataclass
class _OutputBudget:
    limit: int
    total: int = 0
    truncated: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    exceeded: asyncio.Event = field(default_factory=asyncio.Event)


def _docker_command(
    executable: str, container_name: str, image: str, timeout_seconds: int
) -> list[str]:
    return [
        executable,
        "run",
        "--rm",
        "--interactive",
        "--name",
        container_name,
        "--pull",
        "never",
        "--log-driver",
        "none",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--security-opt",
        "seccomp=builtin",
        "--pids-limit",
        PIDS_LIMIT,
        "--memory",
        MEMORY_LIMIT,
        "--memory-swap",
        MEMORY_LIMIT,
        "--cpus",
        CPU_LIMIT,
        "--ulimit",
        f"nofile={NOFILE_LIMIT}",
        "--ulimit",
        "core=0:0",
        "--user",
        "65534:65534",
        "--workdir",
        "/tmp",
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,nodev,size={TMPFS_LIMIT}",
        "--env",
        "HOME=/tmp",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        image,
        "timeout",
        "-s",
        "KILL",
        str(timeout_seconds),
        "python",
        "-I",
        "-",
    ]


async def _read_bounded(
    stream: asyncio.StreamReader, chunks: list[bytes], budget: _OutputBudget
) -> None:
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            return
        async with budget.lock:
            remaining = budget.limit - budget.total
            if remaining > 0:
                accepted = chunk[:remaining]
                chunks.append(accepted)
                budget.total += len(accepted)
            if len(chunk) > remaining:
                budget.truncated = True
                budget.exceeded.set()
                return


async def _remove_container(executable: str, container_name: str) -> None:
    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            "rm",
            "--force",
            container_name,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except TimeoutError:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def _stop_process(
    process: asyncio.subprocess.Process, executable: str, container_name: str
) -> None:
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except TimeoutError:
            pass
    await _remove_container(executable, container_name)


async def execute_python(code: str, timeout_seconds: int | None = None) -> dict[str, Any]:
    """Execute Python in an ephemeral, resource-limited Docker container with no network.

    Use this for calculations, parsing, transformations, simulations, and other self-contained
    Python work. The container has no internet, host mounts, Docker socket, added capabilities, or
    writable root filesystem. Only standard-library modules included in the configured image are
    available. Print values that should be returned. Do not use this for simple arithmetic that the
    calculator tool can handle.
    """
    settings = get_settings()
    if not code or len(code) > settings.python_sandbox_max_code_chars:
        raise ValueError(
            f"Python code must contain 1 to {settings.python_sandbox_max_code_chars} characters"
        )
    requested_timeout = (
        settings.python_sandbox_timeout_seconds if timeout_seconds is None else timeout_seconds
    )
    if requested_timeout < 1 or requested_timeout > settings.python_sandbox_max_timeout_seconds:
        raise ValueError(
            f"timeout_seconds must be between 1 and {settings.python_sandbox_max_timeout_seconds}"
        )

    container_name = f"pi-assistant-python-{uuid.uuid4().hex}"
    command = _docker_command(
        settings.python_sandbox_docker_executable,
        container_name,
        settings.python_sandbox_image,
        requested_timeout + 1,
    )
    started = time.monotonic()
    try:
        process = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=settings.python_sandbox_start_timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Docker is not installed or is not on PATH") from exc
    except TimeoutError as exc:
        await _remove_container(settings.python_sandbox_docker_executable, container_name)
        raise RuntimeError("Docker did not start the sandbox container in time") from exc

    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    budget = _OutputBudget(settings.python_sandbox_max_output_bytes)
    stdout_task = asyncio.create_task(_read_bounded(process.stdout, stdout_chunks, budget))
    stderr_task = asyncio.create_task(_read_bounded(process.stderr, stderr_chunks, budget))
    wait_task = asyncio.create_task(process.wait())
    exceeded_task = asyncio.create_task(budget.exceeded.wait())
    timed_out = False

    try:
        process.stdin.write(code.encode("utf-8"))
        await asyncio.wait_for(process.stdin.drain(), timeout=requested_timeout)
        process.stdin.close()

        done, _pending = await asyncio.wait(
            {wait_task, exceeded_task},
            timeout=requested_timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            timed_out = True
            await _stop_process(process, settings.python_sandbox_docker_executable, container_name)
        elif exceeded_task in done and budget.exceeded.is_set():
            await _stop_process(process, settings.python_sandbox_docker_executable, container_name)
        else:
            await wait_task
    except TimeoutError:
        timed_out = True
        await _stop_process(process, settings.python_sandbox_docker_executable, container_name)
    except asyncio.CancelledError:
        await _stop_process(process, settings.python_sandbox_docker_executable, container_name)
        raise
    finally:
        exceeded_task.cancel()
        if not wait_task.done():
            wait_task.cancel()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

    return {
        "exit_code": process.returncode,
        "stdout": b"".join(stdout_chunks).decode("utf-8", errors="replace"),
        "stderr": b"".join(stderr_chunks).decode("utf-8", errors="replace"),
        "timed_out": timed_out,
        "output_truncated": budget.truncated,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
