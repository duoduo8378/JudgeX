"""结构层：diff 范围、禁用 API、测试文件篡改、绕过式异常处理检测。

这一层拦截「代码能跑通但实现方式违规」的候选解，是判分体系里
最容易漏掉、但最能拉开区分度的一层。
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class Violation:
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.detail}"


@dataclass
class Rule:
    """结构约束规则。"""
    name: str
    # 允许修改的文件（正则）
    allowed_paths: list[str] = field(default_factory=list)
    # 禁止触碰的文件模式
    forbidden_paths: list[str] = field(
        default_factory=lambda: [
            r"(^|/)tests?/",
            r"(^|/)spec/",
            r"_test\.go$",
            r"test_.*\.py$",
            r".*_spec\.ts$",
            r"Test\.java$",
        ]
    )
    # 禁用的 API / 调用模式
    forbidden_patterns: list[str] = field(default_factory=list)
    # 删除行数上限（超过视为疑似删除既有功能）
    max_deleted_lines: int = 50
    # 是否检测空 catch 块
    detect_empty_except: bool = True


class StructureChecker:
    def __init__(self, rule: Rule):
        self.rule = rule

    def check(self, diff: list[dict], changed_files: list[str]) -> list[Violation]:
        """
        diff: [{"path": str, "added": int, "deleted": int, "content": str}, ...]
        """
        v: list[Violation] = []
        r = self.rule

        # 1. 越界修改 + 测试文件篡改
        for path in changed_files:
            if any(re.search(p, path) for p in r.forbidden_paths):
                v.append(Violation(
                    "测试文件篡改",
                    f"修改了 {path}，禁止通过改测试让判分变绿",
                ))
            if r.allowed_paths and not any(re.match(p, path) for p in r.allowed_paths):
                v.append(Violation("越界修改", f"{path} 不在允许修改范围内"))

        # 2. 疑似删除既有功能
        total_deleted = sum(d.get("deleted", 0) for d in diff)
        if total_deleted > r.max_deleted_lines:
            v.append(Violation(
                "疑似删除既有功能",
                f"删除 {total_deleted} 行，超过阈值 {r.max_deleted_lines}",
            ))

        # 3. 禁用 API + AST 检查
        for item in diff:
            content = item.get("content", "")
            for pat in r.forbidden_patterns:
                if re.search(pat, content):
                    v.append(Violation(
                        "禁用API", f"{item['path']} 中出现禁止模式 {pat}",
                    ))
            if r.detect_empty_except and content:
                v.extend(self._check_empty_except(item["path"], content))

        return v

    def _check_empty_except(self, path: str, content: str) -> list[Violation]:
        """检测空 except 块——典型的绕过式异常处理。"""
        out: list[Violation] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return out
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(
                    node.body[0], (ast.Pass, ast.Continue)
                ):
                    out.append(Violation(
                        "绕过式异常处理",
                        f"{path}:{node.lineno} 存在空的 except 块",
                    ))
        return out
