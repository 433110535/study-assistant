"""
沙箱子进程入口。只应由 code_sandbox 启动，不要单独当工具调用。

学生代码在受限 builtins 下执行。审计钩子拦截写文件、子进程和网络连接。
进入学生代码之前设置内存上限：Windows 用 Job Object，其他系统用 resource。
"""
from __future__ import annotations

import builtins
import io
import json
import os
import sys
import traceback


class _Limited(io.TextIOBase):
    def __init__(self, limit: int):
        super().__init__()
        self._parts: list[str] = []
        self._size = 0
        self.limit = limit
        self.truncated = False

    def write(self, text: str) -> int:
        chunk = str(text)
        if self._size >= self.limit:
            self.truncated = True
            return len(chunk)
        room = self.limit - self._size
        if len(chunk) > room:
            self._parts.append(chunk[:room])
            self._size = self.limit
            self.truncated = True
        else:
            self._parts.append(chunk)
            self._size += len(chunk)
        return len(chunk)

    def getvalue(self) -> str:
        body = "".join(self._parts)
        if self.truncated:
            body += "\n…输出已截断"
        return body


def _student_line(exc: BaseException) -> int | None:
    line = None
    tb = exc.__traceback__
    while tb is not None:
        filename = tb.tb_frame.f_code.co_filename
        if filename in {"student.py", "tests.py"}:
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def _install_audit(result_path: str) -> None:
    allowed_write = os.path.abspath(result_path)

    def _audit(event: str, args) -> None:
        if event in {
            "os.system",
            "os.exec",
            "os.posix_spawn",
            "os.spawn",
            "os.remove",
            "os.rmdir",
            "os.rename",
            "os.replace",
            "os.mkdir",
            "os.unlink",
            "subprocess.Popen",
            "ctypes.dlopen",
            "ctypes.dlsym",
            "socket.connect",
            "socket.getaddrinfo",
            "socket.bind",
        }:
            raise PermissionError(f"沙箱拦截了 {event}")
        if event != "open":
            return
        path = os.path.normcase(os.path.abspath(str(args[0]))) if args else ""
        if path == os.path.normcase(allowed_write):
            return
        mode = args[1] if len(args) > 1 and args[1] is not None else "r"
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
        writing = any(flag in str(mode) for flag in ("w", "a", "x", "+"))
        if writing or (flags & 0x3) != 0:
            raise PermissionError("沙箱不允许写文件")

    sys.addaudithook(_audit)


# 持有 Job 句柄。被回收后上限会消失，KILL_ON_JOB_CLOSE 还可能直接结束进程。
_MEMORY_JOB = None


def _memory_message(limit: int) -> str:
    mb = max(1, int(limit) // (1024 * 1024))
    return f"超过 {mb}MB 内存上限"


def _vm_size_bytes() -> int:
    try:
        with open("/proc/self/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmSize:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        return 0
    return 0


def _windows_memory_limit(limit: int) -> None:
    """用 Job Object 限制本进程可提交的内存。resource 在 Windows 上不可用。"""
    global _MEMORY_JOB
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    job_extended = 9
    process_memory = 0x00000100
    job_memory = 0x00000200
    kill_on_close = 0x00002000

    class _BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimit),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(f"CreateJobObject 失败（{ctypes.get_last_error()}）")
    info = _ExtendedLimit()
    info.BasicLimitInformation.LimitFlags = process_memory | job_memory | kill_on_close
    info.ProcessMemoryLimit = limit
    info.JobMemoryLimit = limit
    if not kernel32.SetInformationJobObject(
        job,
        job_extended,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        err = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise OSError(f"SetInformationJobObject 失败（{err}）")
    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        err = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise OSError(f"AssignProcessToJobObject 失败（{err}）")
    _MEMORY_JOB = job


def _posix_memory_limit(limit: int) -> None:
    """限制地址空间。解释器当前占用已经接近上限时，改为再给同样一段。"""
    import resource

    vsize = _vm_size_bytes()
    if vsize > 0 and vsize + 16 * 1024 * 1024 >= limit:
        cap = vsize + limit
    else:
        cap = limit
    try:
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    except (ValueError, OSError):
        cap = max(vsize, limit) + limit
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))


def _apply_memory_limit(limit: int) -> None:
    if limit <= 0:
        raise OSError("内存上限无效")
    if sys.platform == "win32":
        _windows_memory_limit(limit)
        return
    if not sys.platform.startswith(("linux", "darwin", "freebsd")):
        raise OSError("当前系统无法设置子进程内存上限")
    _posix_memory_limit(limit)


def _blank_result(status: str, message: str, exception_type: str) -> dict:
    return {
        "status": status,
        "stdout": "",
        "stderr": "",
        "exception_type": exception_type,
        "exception_message": message[:500],
        "line": None,
        "truncated": False,
    }


def _write_result(path: str, result: dict) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False)
    except MemoryError:
        message = str(result.get("exception_message") or "超过内存上限").replace('"', "")
        body = (
            '{"status":"memory","stdout":"","stderr":"",'
            f'"exception_type":"MemoryError","exception_message":"{message}",'
            '"line":null,"truncated":false}'
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)


def main() -> None:
    policy_path, student_path, tests_path, result_path = sys.argv[1:5]
    with open(policy_path, encoding="utf-8") as handle:
        policy = json.load(handle)
    memory_bytes = int(policy.get("memory_bytes") or 0)
    try:
        _apply_memory_limit(memory_bytes)
    except Exception as exc:
        _write_result(
            result_path,
            _blank_result("error", f"无法设置内存上限：{exc}", "RuntimeError"),
        )
        return
    allowed = set(policy["allowed"])
    safe_names = list(policy["safe_builtins"])
    max_output = int(policy.get("max_output", 4000))

    student_src = open(student_path, encoding="utf-8").read()
    tests_src = open(tests_path, encoding="utf-8").read() if os.path.isfile(tests_path) else ""
    student_code = compile(student_src, "student.py", "exec") if student_src.strip() else None
    tests_code = compile(tests_src, "tests.py", "exec") if tests_src.strip() else None

    stdout = _Limited(max_output)
    stderr = _Limited(max_output)
    sys.stdout = stdout
    sys.stderr = stderr
    sys.setrecursionlimit(200)

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level:
            raise ImportError("不允许相对导入")
        root = name.split(".")[0]
        if root not in allowed:
            raise ImportError(f"沙箱不允许导入 {root}")
        return real_import(name, globals, locals, fromlist, level)

    safe: dict = {}
    for name in safe_names:
        if hasattr(builtins, name):
            safe[name] = getattr(builtins, name)
    safe["__import__"] = guarded_import
    globs = {"__builtins__": safe, "__name__": "__main__"}

    result = {
        "status": "passed",
        "stdout": "",
        "stderr": "",
        "exception_type": "",
        "exception_message": "",
        "line": None,
        "truncated": False,
    }
    _install_audit(result_path)
    try:
        if student_code is not None:
            exec(student_code, globs, globs)
        if tests_code is not None:
            exec(tests_code, globs, globs)
    except MemoryError as exc:
        result["status"] = "memory"
        result["exception_type"] = "MemoryError"
        result["exception_message"] = _memory_message(memory_bytes)
        try:
            result["line"] = _student_line(exc)
        except Exception:
            result["line"] = None
        # 先松开学生代码占住的大块内存，结果文件才写得进去。
        exc.__traceback__ = None
        del exc
        globs.clear()
    except BaseException as exc:
        result["status"] = "failed"
        result["exception_type"] = type(exc).__name__
        result["exception_message"] = str(exc).replace("\n", " ")[:500]
        result["line"] = _student_line(exc)
        stderr.write(traceback.format_exc(limit=8))

    try:
        result["stdout"] = stdout.getvalue()
        result["stderr"] = stderr.getvalue()
        result["truncated"] = bool(stdout.truncated or stderr.truncated)
    except MemoryError:
        result["stdout"] = ""
        result["stderr"] = ""
        result["truncated"] = False
        if result.get("status") == "passed":
            result["status"] = "memory"
            result["exception_type"] = "MemoryError"
            result["exception_message"] = _memory_message(memory_bytes)
    _write_result(result_path, result)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # 结果文件由父进程判断缺失
        traceback.print_exc()
        raise SystemExit(1)
