"""
本机代码沙箱。

独立进程 + 导入白名单 + 审计钩子（禁写文件、禁子进程、禁联网）+ 超时 + 内存上限。
没有容器，只适合本机教学，不要对公网开放。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

HARNESS_PATH = Path(__file__).resolve().parent / "sandbox_harness.py"

MAX_SOURCE_CHARS = 20_000
MAX_OUTPUT_CHARS = 4_000
DEFAULT_TIMEOUT_S = 2.0
MIN_TIMEOUT_S = 0.5
MAX_TIMEOUT_S = 5.0
# 子进程提交内存上限。Windows 没有 resource，由沙箱进程用 Job Object 生效。
MAX_MEMORY_BYTES = 64 * 1024 * 1024

ALLOWED_MODULES = frozenset(
    {
        "__future__",
        "abc",
        "array",
        "bisect",
        "calendar",
        "cmath",
        "collections",
        "copy",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "heapq",
        "itertools",
        "json",
        "math",
        "numbers",
        "operator",
        "pprint",
        "random",
        "re",
        "statistics",
        "string",
        "textwrap",
        "typing",
        "unicodedata",
    }
)

FORBIDDEN_CALLS = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "copyright",
        "credits",
        "delattr",
        "eval",
        "exec",
        "exit",
        "getattr",
        "globals",
        "help",
        "input",
        "license",
        "locals",
        "memoryview",
        "open",
        "quit",
        "setattr",
        "vars",
    }
)

SAFE_DUNDER_DEFS = frozenset(
    {
        "__add__",
        "__bool__",
        "__contains__",
        "__enter__",
        "__eq__",
        "__exit__",
        "__floordiv__",
        "__ge__",
        "__getitem__",
        "__gt__",
        "__hash__",
        "__init__",
        "__iter__",
        "__le__",
        "__len__",
        "__lt__",
        "__mod__",
        "__mul__",
        "__ne__",
        "__next__",
        "__repr__",
        "__setitem__",
        "__str__",
        "__sub__",
        "__truediv__",
    }
)

SAFE_BUILTIN_NAMES = (
    "ArithmeticError",
    "AssertionError",
    "AttributeError",
    "BaseException",
    "EOFError",
    "Ellipsis",
    "Exception",
    "False",
    "FloatingPointError",
    "GeneratorExit",
    "ImportError",
    "IndentationError",
    "IndexError",
    "KeyError",
    "LookupError",
    "MemoryError",
    "NameError",
    "None",
    "NotImplemented",
    "NotImplementedError",
    "OSError",
    "OverflowError",
    "RecursionError",
    "ReferenceError",
    "RuntimeError",
    "StopIteration",
    "SyntaxError",
    "TabError",
    "True",
    "TypeError",
    "UnboundLocalError",
    "UnicodeError",
    "ValueError",
    "Warning",
    "ZeroDivisionError",
    "__build_class__",
    "abs",
    "all",
    "any",
    "ascii",
    "bin",
    "bool",
    "bytearray",
    "bytes",
    "callable",
    "chr",
    "classmethod",
    "complex",
    "dict",
    "dir",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "format",
    "frozenset",
    "hasattr",
    "hash",
    "hex",
    "id",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "object",
    "oct",
    "ord",
    "pow",
    "print",
    "property",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "staticmethod",
    "str",
    "sum",
    "super",
    "tuple",
    "type",
    "zip",
)

_CATEGORIES = {
    "AssertionError": "测试未通过",
    "ImportError": "导入了沙箱不允许的模块",
    "IndentationError": "缩进错误",
    "IndexError": "下标越界",
    "KeyError": "字典里没有这个键",
    "MemoryError": "超过内存上限",
    "NameError": "用到了还没有定义的名字",
    "PermissionError": "试图访问文件、进程或网络",
    "RecursionError": "递归没有停下来",
    "SyntaxError": "语法错误",
    "TabError": "缩进混用了空格和制表符",
    "TimeoutError": "运行超时",
    "TypeError": "参数个数或类型不匹配",
    "ValueError": "值不合法",
    "ZeroDivisionError": "除数为 0",
}

_DIRECTIONS = {
    "AssertionError": "对照断言里的期望值，看返回值差在哪里。不要把实现改成写死的期望结果。",
    "ImportError": "只使用数学和数据结构相关的标准库，例如 math、collections。",
    "IndentationError": "检查冒号下一行是否多缩进了一级，以及同一块是否对齐。",
    "IndexError": "检查下标是否落在序列长度之内，包括空序列。",
    "KeyError": "检查这个键是否已经放进字典，大小写是否一致。",
    "MemoryError": "检查循环里是否在不断拼接字符串，或不断把大块数据放进列表。",
    "NameError": "检查名字是否写错，以及是否先定义再使用。",
    "PermissionError": "去掉文件、系统命令和网络相关的调用，只保留计算逻辑。",
    "RecursionError": "检查递归是否会走到终止条件，以及终止条件是否写反。",
    "SyntaxError": "检查括号、引号和冒号是否成对。",
    "TabError": "把缩进统一成空格。",
    "TimeoutError": "检查循环或递归会不会停不下来。",
    "TypeError": "检查函数定义和调用的参数个数、类型是否一致。",
    "ValueError": "检查传入的值是否落在函数允许的范围内。",
    "ZeroDivisionError": "检查除数是不是 0，包括循环过程中变成 0 的情况。",
}

_POLICIES = {
    1: "第 1 级：只说明错误类别。不要指出行号，不要引用异常原文，不要给出任何修改后的代码。",
    2: "第 2 级：可以指出行号和异常原文。仍然不要给出修改后的代码。",
    3: "第 3 级：可以用一句话说明检查方向。不要贴出完整的正确实现。",
}

_TRACEBACK_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*): ?(.*)$",
    re.M,
)
_LINE_RE = re.compile(r'File "(?:student|tests)\.py", line (\d+)')


def _child_env() -> Dict[str, str]:
    """只保留解释器启动需要的变量，不把密钥传进子进程。"""
    env: Dict[str, str] = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    for key in ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "TEMP", "TMP"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _clamp_timeout(timeout_s: float) -> float:
    try:
        value = float(timeout_s)
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT_S
    return min(MAX_TIMEOUT_S, max(MIN_TIMEOUT_S, value))


def _empty_result(status: str, message: str, exception_type: str = "") -> Dict[str, Any]:
    return {
        "status": status,
        "stdout": "",
        "stderr": "",
        "exception_type": exception_type,
        "exception_message": message,
        "line": None,
        "truncated": False,
        "latency_ms": 0,
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


class _PolicyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in ALLOWED_MODULES:
                self.errors.append(f"不允许导入 {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level and node.level > 0:
            self.errors.append("不允许相对导入")
        else:
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_MODULES:
                self.errors.append(f"不允许导入 {node.module or '（空）'}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in FORBIDDEN_CALLS:
            self.errors.append(f"不允许调用 {name}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            self.errors.append(f"不允许访问 {node.attr}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__") and node.id != "__name__":
            self.errors.append(f"不允许使用名称 {node.id}")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("__") and node.name not in SAFE_DUNDER_DEFS:
            self.errors.append(f"不允许定义 {node.name}")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name.startswith("__") and node.name not in SAFE_DUNDER_DEFS:
            self.errors.append(f"不允许定义 {node.name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name.startswith("__"):
            self.errors.append(f"不允许定义 {node.name}")
        self.generic_visit(node)


def check_source(source: str, label: str) -> list[str]:
    if "\x00" in source:
        return [f"{label}含有非法空字符"]
    if len(source) > MAX_SOURCE_CHARS:
        return [f"{label}超过 {MAX_SOURCE_CHARS} 字符"]
    try:
        tree = ast.parse(source, filename=label)
    except SyntaxError as exc:
        where = f"第 {exc.lineno} 行" if exc.lineno else ""
        return [f"{label}语法错误{where}：{exc.msg}"]
    visitor = _PolicyVisitor()
    visitor.visit(tree)
    return [f"{label}：{item}" for item in visitor.errors]


def _syntax_failure(message: str) -> Dict[str, Any]:
    line = None
    match = re.search(r"第 (\d+) 行", message)
    if match:
        line = int(match.group(1))
    return {
        "status": "failed",
        "stdout": "",
        "stderr": "",
        "exception_type": "SyntaxError",
        "exception_message": message,
        "line": line,
        "truncated": False,
        "latency_ms": 0,
    }


def run_student_code(
    code: str,
    tests: str = "",
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Dict[str, Any]:
    """运行学生代码。tests 非空时在同一环境里继续执行断言。"""
    code = code or ""
    tests = tests or ""
    if not code.strip() and not tests.strip():
        return _empty_result("rejected", "没有可运行的代码")

    code_errors = check_source(code, "代码") if code.strip() else []
    if code_errors and code_errors[0].startswith("代码语法错误"):
        return _syntax_failure(code_errors[0])
    test_errors = check_source(tests, "测试") if tests.strip() else []
    if test_errors and test_errors[0].startswith("测试语法错误"):
        return _syntax_failure(test_errors[0])
    policy_errors = [
        item
        for item in code_errors + test_errors
        if "语法错误" not in item
    ]
    if policy_errors:
        return _empty_result("rejected", "；".join(policy_errors))

    timeout = _clamp_timeout(timeout_s)
    policy = {
        "allowed": sorted(ALLOWED_MODULES),
        "safe_builtins": list(SAFE_BUILTIN_NAMES),
        "max_output": MAX_OUTPUT_CHARS,
        "memory_bytes": MAX_MEMORY_BYTES,
    }
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    with tempfile.TemporaryDirectory(prefix="code_sandbox_", ignore_cleanup_errors=True) as work:
        work_dir = Path(work)
        policy_path = work_dir / "policy.json"
        student_path = work_dir / "student.py"
        tests_path = work_dir / "tests.py"
        result_path = work_dir / "result.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        student_path.write_text(code, encoding="utf-8")
        tests_path.write_text(tests, encoding="utf-8")
        command = [
            sys.executable,
            "-I",
            "-B",
            str(HARNESS_PATH),
            str(policy_path),
            str(student_path),
            str(tests_path),
            str(result_path),
        ]
        proc = None
        job_handle = None
        stdout_text = ""
        stderr_text = ""
        try:
            if sys.platform == "win32":
                try:
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

                    job = kernel32.CreateJobObjectW(None, None)
                    if job:
                        info = _ExtendedLimit()
                        info.BasicLimitInformation.LimitFlags = kill_on_close | process_memory | job_memory
                        info.ProcessMemoryLimit = MAX_MEMORY_BYTES
                        info.JobMemoryLimit = MAX_MEMORY_BYTES
                        kernel32.SetInformationJobObject(job, job_extended, ctypes.byref(info), ctypes.sizeof(info))
                        job_handle = job
                except Exception:
                    job_handle = None

            proc = subprocess.Popen(
                command,
                cwd=work,
                env=_child_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )

            if job_handle and proc:
                try:
                    import ctypes
                    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    proc_handle = getattr(proc, "_handle", None)
                    if proc_handle:
                        kernel32.AssignProcessToJobObject(job_handle, int(proc_handle))
                except Exception:
                    pass

            stdout_text, stderr_text = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
                if sys.platform == "win32":
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                            check=False,
                        )
                    except Exception:
                        pass
                try:
                    out, _ = proc.communicate(timeout=0.5)
                    stdout_text = out or ""
                except Exception:
                    pass
            return {
                "status": "timeout",
                "stdout": str(stdout_text)[:MAX_OUTPUT_CHARS],
                "stderr": "",
                "exception_type": "TimeoutError",
                "exception_message": f"超过 {timeout:g} 秒仍未结束",
                "line": None,
                "truncated": False,
                "latency_ms": int(timeout * 1000),
            }
        finally:
            if job_handle:
                try:
                    import ctypes
                    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    kernel32.CloseHandle(job_handle)
                except Exception:
                    pass

        if not result_path.is_file():
            detail = (stderr_text or stdout_text or "沙箱没有返回结果").strip()
            if "MemoryError" in detail or "内存上限" in detail:
                return _empty_result(
                    "memory",
                    f"超过 {MAX_MEMORY_BYTES // (1024 * 1024)}MB 内存上限",
                    "MemoryError",
                )
            return _empty_result("error", detail[:500], "RuntimeError")

        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _empty_result("error", "沙箱结果无法解析", "RuntimeError")
        result["latency_ms"] = 0
        return result


def format_run_result(result: Dict[str, Any]) -> str:
    """给 Agent 看的纯文本。不含学生源码。"""
    status = result.get("status") or "error"
    exception_type = result.get("exception_type") or "无"
    message = result.get("exception_message") or "无"
    line = result.get("line") if result.get("line") else "无"
    stdout = result.get("stdout") or "（空）"
    lines = [
        f"状态: {status}",
        f"异常: {exception_type}",
        f"信息: {message}",
        f"行号: {line}",
        "标准输出:",
        stdout,
    ]
    if result.get("stderr"):
        lines.append("标准错误: 已记录。解释时不要复述源码，也不要给出改正后的代码。")
    if status != "passed":
        lines.append("下一步：先 explain_traceback，再 hint_level（默认 1）。不要直接给出改正后的完整代码。")
    return "\n".join(lines)


def _parse_observation(text: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "status": "",
        "exception_type": "",
        "exception_message": "",
        "line": None,
    }
    for raw in (text or "").splitlines():
        if raw.startswith("状态:"):
            info["status"] = raw.split(":", 1)[1].strip()
        elif raw.startswith("异常:"):
            value = raw.split(":", 1)[1].strip()
            info["exception_type"] = "" if value == "无" else value
        elif raw.startswith("信息:"):
            value = raw.split(":", 1)[1].strip()
            info["exception_message"] = "" if value == "无" else value
        elif raw.startswith("行号:"):
            value = raw.split(":", 1)[1].strip()
            if value.isdigit():
                info["line"] = int(value)
    if not info["exception_type"]:
        match = _TRACEBACK_RE.search(text or "")
        if match and match.group(1).endswith(("Error", "Exception", "Interrupt")):
            info["exception_type"] = match.group(1)
            info["exception_message"] = info["exception_message"] or match.group(2).strip()
    if info["line"] is None:
        line_match = _LINE_RE.search(text or "")
        if line_match:
            info["line"] = int(line_match.group(1))
    if not info["status"] and info["exception_type"] == "TimeoutError":
        info["status"] = "timeout"
    return info


def explain_traceback(text: str) -> str:
    """把运行结果翻译成学生能读的说明，不提供改正后的代码。"""
    info = _parse_observation(text)
    status = info["status"]
    if status == "passed" and not info["exception_type"]:
        return "这次运行没有异常。"
    if status == "timeout" or info["exception_type"] == "TimeoutError":
        return "程序在时限内没有结束。通常是循环停不下来，或递归没有走到终止条件。这里只说明现象，不给出改正后的代码。"
    if status == "memory" or info["exception_type"] == "MemoryError":
        return "程序超过了内存上限。通常是列表、字符串或大块数据一直变大。这里只说明现象，不给出改正后的代码。"
    if status == "rejected":
        reason = info["exception_message"] or "使用了不允许的操作"
        return f"代码在运行前被沙箱拒绝：{reason}。请改成普通计算后再运行。"
    if status == "error":
        return f"沙箱自己没有跑完：{info['exception_message'] or '未知错误'}。"
    kind = info["exception_type"] or "异常"
    category = _CATEGORIES.get(kind, "运行时错误")
    where = f"位置在第 {info['line']} 行。" if info["line"] else ""
    detail = info["exception_message"] or "（无更多信息）"
    return f"这是{category}（{kind}）。异常信息是：{detail}。{where}这里只解释错误，不给出改正后的代码。"


def hint_for_level(level: int = 1, observation: str = "") -> str:
    """按级别返回允许告诉学生的内容。级别越高，信息越多，仍然不给完整答案。"""
    try:
        chosen = int(level)
    except (TypeError, ValueError):
        chosen = 1
    chosen = min(3, max(1, chosen))
    info = _parse_observation(observation)
    kind = info["exception_type"]
    if info["status"] == "timeout":
        kind = "TimeoutError"
    if info["status"] == "memory":
        kind = "MemoryError"
    if info["status"] == "rejected":
        message = info["exception_message"] or ""
        kind = "ImportError" if "不允许导入" in message else "PermissionError"
    category = _CATEGORIES.get(kind, "运行没有通过")
    lines = [_POLICIES[chosen], f"错误类别：{category}"]
    if chosen >= 2 and info.get("line"):
        lines.append(f"行号：{info['line']}")
    if chosen >= 2 and kind:
        message = info["exception_message"] or ""
        lines.append(f"异常原文：{kind}: {message}".rstrip())
    if chosen >= 3:
        lines.append("检查方向：" + _DIRECTIONS.get(kind, "按报错逐行核对，先不要重写整段代码。"))
    lines.append("不要输出修改后的完整代码。")
    return "\n".join(lines)


def record_code_run(
    user_id: str,
    code: str,
    tests: str,
    result: Dict[str, Any],
) -> Optional[str]:
    """页面上的一次运行写入 trace。失败时不影响页面。"""
    try:
        from backend.platform.trace_store import TraceRun

        preview = (code or tests or "").strip().splitlines()
        head = "\n".join(preview[:8])[:500]
        tool_name = "run_tests" if (tests or "").strip() else "run_code"
        trace = TraceRun(user_input=f"[代码助教]\n{head}", session_id=user_id or "student")
        trace.start()
        summary = format_run_result(result)
        trace.log_tool_call(
            tool_name,
            {"timeout_s": DEFAULT_TIMEOUT_S, "chars": len(code or "")},
            summary,
            str(result.get("status") or "error"),
            int(result.get("latency_ms") or 0),
        )
        trace.finish(summary, iterations=1, status="ok" if result.get("status") == "passed" else "error")
        return trace.run_id
    except Exception:
        return None
