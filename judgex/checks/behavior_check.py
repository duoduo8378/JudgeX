"""动态层：目标用例、边界用例、回归套件执行。

关键设计：必须同时跑目标用例和回归套件。
只跑目标用例时，候选解可以通过删除无关代码让测试变绿；
加上回归套件后，这类作弊解法会被立即拦截。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class CaseGroup:
    name: str
    command: list[list[str]]   # 每条用例一条命令，退出码 0 为通过
    weight: float
    total: int


@dataclass
class GroupResult:
    name: str
    passed: int
    total: int
    weight: float

    @property
    def score(self) -> float:
        return self.weight * (self.passed / self.total) if self.total else 0.0

    def __str__(self) -> str:
        mark = "✓" if self.passed == self.total else "✗"
        return f"{mark} {self.name} {self.passed}/{self.total}  ({self.score:.0f}/{self.weight:.0f})"


class BehaviorChecker:
    def __init__(self, groups: list[CaseGroup], workdir: str):
        self.groups = groups
        self.workdir = workdir

    def _count_passed(self, cmds: list[list[str]]) -> tuple[int, int]:
        """
        真实项目中应解析 pytest / go test 的 XML 报告统计通过数。
        此处用逐条执行 + 退出码的简化实现，保持零依赖可运行。
        """
        passed = 0
        for cmd in cmds:
            try:
                proc = subprocess.run(
                    cmd, cwd=self.workdir,
                    capture_output=True, text=True, timeout=300,
                )
                if proc.returncode == 0:
                    passed += 1
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        return passed, len(cmds)

    def run(self) -> list[GroupResult]:
        return [
            GroupResult(g.name, *self._count_passed(g.command), g.weight)
            for g in self.groups
        ]
