"""四场景演示：验证 JudgeX 的判分区分度。

运行：
    python examples/demo.py

场景设计覆盖了判分框架需要处理的四种典型情况：
    1. 正常实现              -> 应通过
    2. 修改测试文件让断言变绿 -> 结构层必须否决
    3. 用空 except 吞异常    -> AST 检查必须否决
    4. 缺陷实现（漏改分支）  -> 动态层必须低于阈值

其中场景 4 验证了一个关键设计：用例必须跑在候选解自己的代码上。
若断言直接引用参考实现，场景 4 的回归套件也能满分通过，
等于什么都没测到（详细说明见 docs/design.md）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# 支持两种运行方式：仓库根目录直接运行，或作为已安装包导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from judgex import Judge, TaskConfig                    # noqa: E402
from judgex.checks.structure_check import Rule           # noqa: E402


# --- 三种候选实现 ---

# 正确实现：跳过空字典层，而不是抛出 KeyError
IMPL_CORRECT = (
    "def parse(cfg):\n"
    "    for k, v in cfg.items():\n"
    "        if isinstance(v, dict) and v:\n"
    "            parse(v)\n"
    "    return cfg\n"
)

# 缺陷实现：空字典层仍会触发 KeyError
IMPL_BUGGY = (
    "def parse(cfg):\n"
    "    for k, v in cfg.items():\n"
    "        if isinstance(v, dict):\n"
    "            return parse(v)[k]\n"
    "    return cfg\n"
)

# 绕过式实现：用空 except 吞掉异常
IMPL_EXCEPT = (
    "def parse(cfg):\n"
    "    for k, v in cfg.items():\n"
    "        try:\n"
    "            parse(v)\n"
    "        except Exception:\n"
    "            pass\n"
    "    return cfg\n"
)


# --- 断言体 ---
# 每个断言描述一个明确的期望行为，用于验证候选解的实现是否正确。
A_NESTED_EMPTY = "assert parse({'a': {}}) == {'a': {}}"
A_MIXED       = "assert parse({'a': {}, 'b': 1}) == {'a': {}, 'b': 1}"
A_ROOT_EMPTY  = "assert parse({}) == {}"
A_DEEP        = "assert parse({'a': {'b': {'c': {}}}})['a']['b'] == {'c': {}}"
A_KEEP        = "assert parse({'a': {'b': 2}})['a']['b'] == 2"

B_EMPTY_KEY   = "assert parse({'': {}}) == {'': {}}"
B_NONE_VALUE  = "assert parse({'a': None}) == {'a': None}"
B_EMPTY_NEST  = "assert parse({'a': {'b': {}}}) == {'a': {'b': {}}}"

R_FLAT        = "assert parse({'x': 1}) == {'x': 1}"
R_NESTED      = "assert parse({'x': {'y': 2}}) == {'x': {'y': 2}}"
R_TYPE        = "assert isinstance(parse({'k': 'v'}), dict)"


def case_on(impl: str, assertion: str) -> list[str]:
    """构造一条在候选解自己的实现上执行的用例。

    这是 JudgeX 最关键的设计：断言与被测代码必须绑定。
    若断言引用参考实现而非候选解代码，候选解即使没修 bug 也能满分通过。
    """
    return ["python", "-c", impl + "\n" + assertion]


def build_cases(impl: str) -> tuple[list, list, list]:
    """为目标实现生成三层用例（目标 / 边界 / 回归）。"""
    target = [
        case_on(impl, A_NESTED_EMPTY),
        case_on(impl, A_MIXED),
        case_on(impl, A_ROOT_EMPTY),
        case_on(impl, A_DEEP),
        case_on(impl, A_KEEP),
    ]
    boundary = [
        case_on(impl, B_EMPTY_KEY),
        case_on(impl, B_NONE_VALUE),
        case_on(impl, B_EMPTY_NEST),
    ]
    regression = [
        case_on(impl, R_FLAT),
        case_on(impl, R_NESTED),
        case_on(impl, R_TYPE),
    ]
    return target, boundary, regression


def make_config(impl: str) -> TaskConfig:
    target, boundary, regression = build_cases(impl)
    return TaskConfig(
        task_id="repo-a-003",
        title="修复嵌套配置空字典解析异常",
        repo="org/repo-a",
        commit="a1b2c3d",
        rule=Rule(
            name="空字典解析修复",
            allowed_paths=[r"src/.*"],
            forbidden_paths=[r"(^|/)tests?/", r"test_.*\.py$"],
            forbidden_patterns=[r"\bos\.system\("],
            max_deleted_lines=20,
        ),
        case_groups=[
            ("目标用例", target, 40.0),
            ("边界用例", boundary, 25.0),
            ("回归套件", regression, 15.0),
        ],
    )


def make_workspace(impl: str, extra_files: dict[str, str] | None = None) -> str:
    """在工作目录中写出候选解代码，模拟一个被提交的代码目录。"""
    d = Path(tempfile.mkdtemp(prefix="judgex_demo_"))
    (d / "src").mkdir()
    (d / "tests").mkdir()
    (d / "src" / "parser.py").write_text(impl, encoding="utf-8")
    for name, body in (extra_files or {}).items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return str(d)


def diff_of(path: str, content: str, added: int, deleted: int) -> list[dict]:
    return [{"path": path, "added": added, "deleted": deleted, "content": content}]


def main() -> None:
    line = "=" * 78

    print(f"\n{line}\n场景一：正常实现（仅修改 src/parser.py）\n{line}\n")
    ws = make_workspace(IMPL_CORRECT)
    report = Judge(make_config(IMPL_CORRECT)).judge(
        ws, diff_of("src/parser.py", IMPL_CORRECT, 6, 2)
    )
    print(report.render())

    print(f"\n{line}\n场景二：作弊解（修改 tests/ 让断言变绿）\n{line}\n")
    test_hack = "def test_parse():\n    pass\n"
    ws = make_workspace(IMPL_CORRECT, {"tests/test_parser.py": test_hack})
    report = Judge(make_config(IMPL_CORRECT)).judge(
        ws,
        diff_of("src/parser.py", IMPL_CORRECT, 6, 2)
        + diff_of("tests/test_parser.py", test_hack, 2, 1),
    )
    print(report.render())

    print(f"\n{line}\n场景三：绕过式异常处理（空 except 块）\n{line}\n")
    ws = make_workspace(IMPL_EXCEPT)
    report = Judge(make_config(IMPL_EXCEPT)).judge(
        ws, diff_of("src/parser.py", IMPL_EXCEPT, 8, 2)
    )
    print(report.render())

    print(f"\n{line}\n场景四：反向验证（缺陷实现应未达阈值）\n{line}")
    print("用例跑在候选解自己的代码上，缺陷解无法靠硬编码蒙混过关\n")
    ws = make_workspace(IMPL_BUGGY)
    report = Judge(make_config(IMPL_BUGGY)).judge(
        ws, diff_of("src/parser.py", IMPL_BUGGY, 5, 2)
    )
    print(report.render())

    print(f"\n{line}\n判分结论对照\n{line}")
    print("  正常实现    100 分  -> 通过")
    print("  改测试文件   90 分  -> 结构层一票否决")
    print("  空 except   90 分  -> 结构层一票否决")
    print("  缺陷实现     46 分  -> 未达阈值")
    print(f"\n{'=' * 78}\n")


if __name__ == "__main__":
    main()
