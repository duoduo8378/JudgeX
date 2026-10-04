"""三层判分框架 · 主模块

作品：AI Coding 任务设计
说明：把主观的代码质量判断，转成可自动执行的断言。

设计要点：
1. 三层串联（静态 / 结构 / 动态），任一否决层失败直接判 0。
2. 动态层必须同时跑「目标用例」和「回归套件」——只跑目标用例时，
   候选解可以通过删改无关代码让测试变绿，加上回归后这类作弊被立即拦截。
3. 纯标准库实现，零依赖，可直接运行：python run_demo.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime

from .checks.static_check import StaticChecker
from .checks.structure_check import StructureChecker, Rule, Violation
from .checks.behavior_check import BehaviorChecker, CaseGroup


@dataclass
class TaskConfig:
    task_id: str
    title: str
    repo: str
    commit: str
    # 动态层是判分主体：代码只要能编译通过不等于做对了，
    # 行为正确性必须占绝对权重，否则「能跑但错」会混过高分。
    static_weight: float = 10.0
    structure_weight: float = 10.0
    pass_threshold: float = 60.0
    rule: Rule = field(default_factory=Rule)
    # 动态层用例组：(名称, 命令列表, 权重)
    case_groups: list[tuple[str, list[list[str]], float]] = field(default_factory=list)


@dataclass
class JudgeReport:
    task_id: str
    title: str
    candidate: str
    static_score: float
    structure_score: float
    behavior_score: float
    total_score: float
    violations: list[str]
    verdicts: list[str]
    rejected: bool
    reject_reason: str
    verdict: str
    created_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def render(self) -> str:
        line = "=" * 52
        out = [
            line,
            f"任务: {self.task_id} / {self.title}",
            f"候选解: {self.candidate}",
            "-" * 52,
            f"[静态层]   {'  '.join(self.verdicts[:2])}",
            f"          -> {self.static_score:.0f} 分",
            f"[结构层]   违规 {len(self.violations)} 项",
            f"          -> {self.structure_score:.0f} 分",
            f"[动态层]   {'  '.join(self.verdicts[2:])}",
            f"          -> {self.behavior_score:.0f} 分",
            "-" * 52,
            f"总分: {self.total_score:.0f}/100   违规: "
            f"{'无' if not self.violations else str(len(self.violations)) + ' 项'}",
        ]
        for v in self.violations:
            out.append(f"         - {v}")
        out += [f"结论: {self.verdict}", line]
        return "\n".join(out)


class Judge:
    def __init__(self, config: TaskConfig):
        self.cfg = config

    def judge(self, candidate_dir: str, diff: list[dict]) -> JudgeReport:
        cfg = self.cfg

        # ---- 静态层（一票否决）----
        static_results = StaticChecker(candidate_dir).run()
        static_ok = all(r.passed for r in static_results)
        static_score = cfg.static_weight if static_ok else 0.0
        verdicts = [str(r) for r in static_results]

        # ---- 结构层（一票否决）----
        changed = [d["path"] for d in diff]
        violations: list[Violation] = StructureChecker(cfg.rule).check(diff, changed)
        structure_ok = not violations
        structure_score = cfg.structure_weight if structure_ok else 0.0

        # ---- 动态层（比例给分）----
        groups = [
            CaseGroup(name, cmds, weight, len(cmds))
            for name, cmds, weight in cfg.case_groups
        ]
        behavior_results = BehaviorChecker(groups, candidate_dir).run()
        behavior_score = sum(r.score for r in behavior_results)
        verdicts.extend(str(r) for r in behavior_results)

        total = static_score + structure_score + behavior_score
        rejected = not (static_ok and structure_ok)

        reason = ""
        if rejected:
            reason = (
                "静态层失败（一票否决）" if not static_ok
                else f"结构层违规：{violations[0].kind}"
            )
        verdict = (
            reason if rejected
            else ("通过" if total >= cfg.pass_threshold else "未达阈值")
        )

        return JudgeReport(
            task_id=cfg.task_id,
            title=cfg.title,
            candidate=candidate_dir,
            static_score=static_score,
            structure_score=structure_score,
            behavior_score=behavior_score,
            total_score=total,
            violations=[str(v) for v in violations],
            verdicts=verdicts,
            rejected=rejected,
            reject_reason=reason,
            verdict=verdict,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
