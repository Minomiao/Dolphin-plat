import sys
import asyncio
import time
import atexit
import signal
import base64
from typing import Dict, Any
from pathlib import Path

from modules.logger import get_logger
from modules.bootstrap import constants

log = get_logger("Dolphin.powershell_manager")

MAX_SCRIPT_LENGTH = constants.MAX_SCRIPT_LENGTH
MAX_OUTPUT_LENGTH = constants.MAX_OUTPUT_LENGTH
MAX_OUTPUT_LINES = constants.MAX_OUTPUT_LINES
DEFAULT_TIMEOUT = constants.DEFAULT_TIMEOUT
DEFAULT_WAIT_TIME = constants.DEFAULT_WAIT_TIME

_running_processes: Dict[str, Dict[str, Any]] = {}
_completed_outputs: Dict[str, Dict[str, Any]] = {}
_process_counter = 0


class _DummySock:
    def close(self):
        pass

    def fileno(self):
        return -1


def _get_work_dir():
    try:
        from modules.main_server import config
        return config.load_config().get('work_directory', 'workplace')
    except Exception:
        return 'workplace'


async def _read_stream(stream: asyncio.StreamReader, buffer: list, max_chars: int = MAX_OUTPUT_LENGTH):
    total = 0
    while total < max_chars:
        try:
            line = await stream.readline()
        except Exception:
            break
        if not line:
            break
        try:
            decoded = line.decode('utf-8', errors='ignore')
        except Exception:
            decoded = line.decode('ascii', errors='ignore')
        buffer.append(decoded)
        total += len(decoded)


def _close_transports(proc_info: dict) -> None:
    process = proc_info['process']
    try:
        proc_info['stdout_task'].cancel()
    except Exception:
        pass
    try:
        proc_info['stderr_task'].cancel()
    except Exception:
        pass
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(process, stream_name, None)
        if stream is not None:
            try:
                tr = getattr(stream, '_transport', None)
                if tr is not None:
                    try:
                        tr.close()
                    except Exception:
                        pass
                    try:
                        tr._sock = _DummySock()
                    except Exception:
                        pass
            except Exception:
                pass
    try:
        if hasattr(process, '_transport') and process._transport is not None:
            try:
                process._transport.close()
            except Exception:
                pass
            try:
                process._transport._sock = _DummySock()
            except Exception:
                pass
    except Exception:
        pass


async def execute_script(script: str, timeout: int = DEFAULT_TIMEOUT, wait_time: int = DEFAULT_WAIT_TIME) -> Dict[str, Any]:
    global _process_counter
    _process_counter += 1
    command_id = f"dps{_process_counter:04d}"

    work_dir = _get_work_dir()
    work_path = Path(work_dir).resolve()
    if not work_path.exists():
        work_path.mkdir(parents=True, exist_ok=True)

    log.info(f"执行脚本: command_id={command_id}, timeout={timeout}s, wait={wait_time}s")

    try:
        process = await _start_process(script, work_path, command_id)

        proc_info = {
            'process': process,
            'script': script[:200],
            'start_time': time.time(),
            'stdout_task': None,
            'stderr_task': None,
            'stdout_buffer': [],
            'stderr_buffer': [],
        }

        stdout_buffer: list = []
        stderr_buffer: list = []
        stdout_task = asyncio.create_task(_read_stream(process.stdout, stdout_buffer))
        stderr_task = asyncio.create_task(_read_stream(process.stderr, stderr_buffer))
        proc_info['stdout_task'] = stdout_task
        proc_info['stderr_task'] = stderr_task
        proc_info['stdout_buffer'] = stdout_buffer
        proc_info['stderr_buffer'] = stderr_buffer

        _running_processes[command_id] = proc_info

        try:
            await asyncio.wait_for(process.wait(), timeout=wait_time)
            await stdout_task
            await stderr_task

            stdout = ''.join(stdout_buffer)
            if len(stdout) > MAX_OUTPUT_LENGTH:
                stdout = stdout[:MAX_OUTPUT_LENGTH] + f"\n... (输出已截断)"

            _close_transports(proc_info)
            _completed_outputs[command_id] = {
                "status": "done",
                "exit_code": process.returncode,
                "output": stdout
            }
            del _running_processes[command_id]

            log.info(f"命令完成: command_id={command_id}, returncode={process.returncode}")

            return {
                "success": True,
                "return_code": process.returncode,
                "output": stdout,
                "completed": True,
                "command_id": command_id,
                "message": f"脚本执行完成，返回码: {process.returncode}"
            }

        except asyncio.TimeoutError:
            await asyncio.sleep(0.1)
            stdout = ''.join(stdout_buffer)

            log.info(f"命令仍在运行: command_id={command_id}, stdout={len(stdout)}字")

            return {
                "success": True,
                "output": stdout if stdout else "(命令正在运行中...)",
                "completed": False,
                "command_id": command_id,
                "wait_time": wait_time,
                "message": f"命令仍在后台运行中 (command_id: {command_id})，可使用 check_script 查询最新输出"
            }

    except Exception as e:
        log.error(f"执行脚本失败: command_id={command_id}, error={str(e)}")
        if command_id in _running_processes:
            _close_transports(_running_processes[command_id])
            del _running_processes[command_id]
        _completed_outputs[command_id] = {
            "status": "done",
            "exit_code": None,
            "output": ""
        }
        return {"error": f"命令执行失败: {str(e)}", "command_id": command_id, "output": ""}


async def check_script(command_id: str, wait_time: int = DEFAULT_WAIT_TIME) -> Dict[str, Any]:
    if command_id not in _running_processes:
        if command_id in _completed_outputs:
            return dict(_completed_outputs[command_id])
        return {
            "status": "done",
            "exit_code": None,
            "output": ""
        }

    proc_info = _running_processes[command_id]
    process = proc_info['process']

    log.info(f"check_script: command_id={command_id}, wait={wait_time}s")

    try:
        await asyncio.wait_for(process.wait(), timeout=wait_time)
        await proc_info['stdout_task']
        await proc_info['stderr_task']

        stdout = ''.join(proc_info['stdout_buffer'])
        return_code = process.returncode

        _close_transports(proc_info)
        _completed_outputs[command_id] = {
            "status": "done",
            "exit_code": return_code,
            "output": stdout
        }
        del _running_processes[command_id]

        log.info(f"命令完成: command_id={command_id}, returncode={return_code}")

        lines = stdout.split('\n')
        if len(lines) > MAX_OUTPUT_LINES:
            stdout = '\n'.join(lines[-MAX_OUTPUT_LINES:]) + f"\n... (输出已截断，共 {len(lines)} 行)"

        return {
            "status": "done",
            "exit_code": return_code,
            "output": stdout
        }

    except asyncio.TimeoutError:
        await asyncio.sleep(0.1)
        stdout = ''.join(proc_info['stdout_buffer'])

        lines = stdout.split('\n')
        if len(lines) > MAX_OUTPUT_LINES:
            stdout = '\n'.join(lines[-MAX_OUTPUT_LINES:]) + f"\n... (输出已截断，共 {len(lines)} 行)"

        log.info(f"命令仍在运行: command_id={command_id}")

        return {
            "status": "running",
            "output": stdout if stdout else "(命令正在运行中...)"
        }


def kill_command(command_id: str) -> Dict[str, Any]:
    if command_id not in _running_processes:
        if command_id in _completed_outputs:
            return dict(_completed_outputs[command_id])
        return {
            "status": "done",
            "exit_code": None,
            "output": ""
        }

    proc_info = _running_processes[command_id]
    process = proc_info['process']

    _close_transports(proc_info)

    try:
        process.kill()
    except Exception as e:
        log.error(f"终止进程失败: command_id={command_id}, error={str(e)}")

    stdout = ''.join(proc_info['stdout_buffer'])
    exit_code = process.returncode

    lines = stdout.split('\n')
    if len(lines) > MAX_OUTPUT_LINES:
        stdout = '\n'.join(lines[-MAX_OUTPUT_LINES:]) + f"\n... (输出已截断，共 {len(lines)} 行)"

    _completed_outputs[command_id] = {
        "status": "done",
        "exit_code": exit_code,
        "output": stdout if stdout else "(命令已被强制终止)"
    }
    del _running_processes[command_id]

    log.info(f"命令已强制终止: command_id={command_id}, exit_code={exit_code}")

    return {
        "status": "done",
        "exit_code": exit_code,
        "output": stdout if stdout else "(命令已被强制终止)"
    }


def _cleanup_all_processes():
    for cid, proc_info in list(_running_processes.items()):
        try:
            process = proc_info['process']
            _close_transports(proc_info)
            if process.returncode is None:
                process.kill()
        except Exception:
            pass
    _running_processes.clear()
    _completed_outputs.clear()


def _signal_handler(signum, frame):
    _cleanup_all_processes()
    sys.exit(0)


atexit.register(_cleanup_all_processes)
try:
    signal.signal(signal.SIGINT, _signal_handler)
except (ValueError, AttributeError):
    pass
try:
    signal.signal(signal.SIGTERM, _signal_handler)
except (ValueError, AttributeError):
    pass


async def _start_process(script: str, work_path: Path, command_id: str = ""):
    wrapper = (
        f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n'
        f'$ErrorActionPreference = "Continue"\n'
        f'{script}\n'
    )
    encoded = base64.b64encode(wrapper.encode('utf-16-le')).decode('ascii')

    log.info(f"启动进程: command_id={command_id}, script_len={len(script)}")

    return await asyncio.create_subprocess_exec(
        'powershell', '-NoProfile', '-EncodedCommand', encoded,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(work_path)
    )
