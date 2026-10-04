"""静态层：格式、语法、构建检查。任一失败即触发一票否决。"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:
        mark = "✓" if self.passed else "✗"
        suffix = f"  ({self.detail})" if self.detail else ""
        return f"{mark} {self.name}{suffix}"


class StaticChecker:
    def __init__(self, workdir: str, commands: list[dict] | None = None):
        self.workdir = workdir
        # 可在任务配置中覆盖为 ruff / mypy / tsc / mvn 等真实命令
        self.commands = commands or [
            {
                "name": "构建",
                "cmd": [
                    "python", "-c",
                    "import compileall,sys;"
                    " sys.exit(0 if compileall.compile_dir('.', quiet=2) else 1)",
                ],
            },
            {
                "name": "语法",
                "cmd": [
                    "python", "-c",
                    "import ast,pathlib;"
                    " [ast.parse(p.read_text(encoding='utf-8'))"
                    " for p in pathlib.Path('.').rglob('*.py')]",
                ],
            },
        ]

    def _run(self, cmd: list[str]) -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                cmd, cwd=self.workdir,
                capture_output=True, text=True, timeout=600,
            )
            tail = (proc.stdout + proc.stderr).strip().splitlines()
            return proc.returncode == 0, (tail[-1][:120] if tail else "")
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return False, str(exc)[:120]

    def run(self) -> list[CheckResult]:
        return [
            CheckResult(spec["name"], *self._run(spec["cmd"]))
            for spec in self.commands
        ]
