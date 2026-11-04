"""
沙箱子进程入口。只应由 code_sandbox 启动，不要单独当工具调用。

学生代码在受限 builtins 下执行。审计钩子拦截写文件、子进程和网络连接。
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


def main() -> None:
    policy_path, student_path, tests_path, result_path = sys.argv[1:5]
    with open(policy_path, encoding="utf-8") as handle:
        policy = json.load(handle)
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
    except BaseException as exc:
        result["status"] = "failed"
        result["exception_type"] = type(exc).__name__
        result["exception_message"] = str(exc).replace("\n", " ")[:500]
        result["line"] = _student_line(exc)
        stderr.write(traceback.format_exc(limit=8))

    result["stdout"] = stdout.getvalue()
    result["stderr"] = stderr.getvalue()
    result["truncated"] = bool(stdout.truncated or stderr.truncated)
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # 结果文件由父进程判断缺失
        traceback.print_exc()
        raise SystemExit(1)
