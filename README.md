# JudgeX · AI Coding 任务三层判分框架

> 把主观的代码质量判断，转成可自动执行的断言。
> 解决 AI Coding 任务中「谁来判分、怎么判才公平、怎么拦住作弊解法」三个核心问题。

[![CI](https://github.com/duoduo8378/JudgeX/actions/workflows/ci.yml/badge.svg)](https://github.com/duoduo8378/JudgeX/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Deps](https://img.shields.io/badge/dependencies-none-brightgreen.svg)]()

---

## 为什么需要这个

AI Coding 任务设计有一个绕不开的难题：**模型产出的代码，怎么判断它是真的做对了，还是只是"看起来对"？**

常见的判分方式是人工阅读 diff 后给结论。这会同时踩三个坑：

| 问题 | 后果 |
|---|---|
| 效率低 | 一个任务几分钟，任务量上不去 |
| 标准不一致 | 同一份代码换个人判结果就变了，评测不可复现 |
| 拦不住作弊解法 | 改测试文件让断言变绿、用 `try/except` 吞掉异常 —— 代码"能跑通"但实际没解决 bug |

JudgeX 用三层自动检查替代人工判断，把标准固化成代码。

---

## 三层判分设计

| 层 | 回答的问题 | 实现方式 | 权重 |
|---|---|---|---|
| **静态层** Static | 代码有没有基本质量、能否构建 | 编译检查、语法解析、lint、类型检查 | 10 |
| **结构层** Structure | 实现方式合不合规 | diff 范围分析、AST 检查、禁用 API | 10 |
| **动态层** Behavior | 行为到底对不对 | 单元测试 + 自研断言脚本 | 80 |

静态层与结构层为**一票否决**层，任一失败直接判 0 分；动态层按用例通过比例给分。

### 权重为什么这样定

这是一个在实践中被验证过的设计。最初的版本是「静态 20 + 结构 20 + 动态 60」，结果一个**有缺陷的实现仍然能拿 61 分越过 60 分阈值** —— 因为它能编译通过、也没有违规操作，只是行为不对。

代码能编译通过 ≠ 做对了。**行为正确性必须占绝对权重**，否则「能跑但错」的解法会混过高分。现在动态层占 80 分，缺陷解正确落榜。

---

## 两个关键设计（踩过坑才知道）

### 一、用例必须跑在候选解自己的代码上

如果断言直接写在用例里、引用的是参考实现，那么候选解交上来的代码**根本没被测到** —— 它可以完全不碰你的 bug 也能拿满分。

```python
# ✗ 错误：断言引用参考实现，候选解代码从未被执行
def test_nested_empty():
    assert reference_parse({'a': {}}) == {'a': {}}

# ✓ 正确：断言跑在候选解提交的代码上
def test_nested_empty(candidate_module):
    assert candidate_module.parse({'a': {}}) == {'a': {}}
```

在 JudgeX 的四场景验证中，仅此一项修复就让缺陷解的行为分从 **80 分掉到 26 分**。

### 二、动态层必须包含回归套件

只测目标用例，候选解可以通过删改无关代码让测试「变绿」。加上原仓库的回归套件后，这类作弊被立即拦截。

```
目标用例：任务要求的新行为
边界用例：空值、极端输入、异常路径
回归套件：原仓库既有行为（必须全过，否则判为破坏既有功能）
```

---

## 快速开始

纯标准库，零第三方依赖。

```bash
git clone https://github.com/duoduo8378/JudgeX.git
cd JudgeX
python examples/demo.py
```

### 输出示例

**场景一：正常实现 → 100 分通过**

```
====================================================
任务: repo-a-003 / 修复嵌套配置空字典解析异常
----------------------------------------------------
[静态层]   ✓ 构建  ✓ 语法
          -> 10 分
[结构层]   违规 0 项
          -> 10 分
[动态层]   ✓ 目标用例 5/5  (40/40)  ✓ 边界用例 3/3  (25/25)  ✓ 回归套件 3/3  (15/15)
          -> 80 分
----------------------------------------------------
总分: 100/100   违规: 无
结论: 通过
====================================================
```

**场景二：修改测试文件让断言变绿 → 结构层一票否决**

```
[结构层]   违规 2 项
          -> 0 分
总分: 90/100   违规: 2 项
         - [测试文件篡改] 修改了 tests/test_parser.py，禁止通过改测试让判分变绿
         - [越界修改] tests/test_parser.py 不在允许修改范围内
结论: 结构层违规：测试文件篡改
```

**场景三：用空 `except` 吞掉异常 → AST 检测拦截**

```
总分: 90/100   违规: 1 项
         - [绕过式异常处理] src/parser.py:5 存在空的 except 块
结论: 结构层违规：绕过式异常处理
```

**场景四：缺陷实现（漏改空字典分支）→ 未达阈值**

```
[动态层]   ✗ 目标用例 1/5  (8/40)  ✗ 边界用例 1/3  (8/25)  ✗ 回归套件 2/3  (10/15)
          -> 26 分
总分: 46/100   违规: 无
结论: 未达阈值
```

四种候选解、三种拦截路径、区分度明确 —— 这就是判分框架该有的样子。

---

## 结构层能识别什么

| 违规类型 | 检测方式 |
|---|---|
| 测试文件篡改 | diff 路径匹配 `test/`、`*_test.go`、`*.spec.ts`、`Test.java` |
| 越界修改 | diff 超出允许文件白名单 |
| 禁用 API | 模式匹配（可自定义，如 `os.system`） |
| 绕过式异常处理 | AST 识别空 `except` 块、仅 `pass`、仅 `continue` |
| 疑似删除既有功能 | diff 删除行数超阈值 |

---

## 项目结构

```
JudgeX/
├── judgex/
│   ├── __init__.py
│   ├── judge.py              # 三层判分主框架
│   └── checks/
│       ├── __init__.py
│       ├── static_check.py   # 静态层：编译、语法
│       ├── structure_check.py# 结构层：diff、AST
│       └── behavior_check.py  # 动态层：用例执行
├── examples/
│   ├── demo.py               # 四场景演示
│   └── example_task.yaml     # 任务配置示例
├── docs/
│   └── design.md             # 设计文档
├── LICENSE
└── README.md
```

## 任务配置示例

见 `examples/example_task.yaml`。核心结构：

```yaml
task:
  id: repo-a-003
  title: 修复嵌套配置空字典解析异常

structure_rules:
  allowed_paths: ["src/.*"]           # 允许修改的范围
  forbidden_paths: ["(^|/)tests?/"]   # 禁触碰的范围
  forbidden_patterns: ["\\bos\\.system\\("]
  max_deleted_lines: 20
  detect_empty_except: true

behavior_cases:
  target:    [...]   # 任务要求的新行为，权重 40
  boundary:  [...]   # 边界与异常输入，权重 25
  regression: [...]  # 原仓库既有行为，权重 15

difficulty_calibration:
  baseline_models:
    - {name: "baseline-A", pass_rate: 0.72}
    - {name: "baseline-B", pass_rate: 0.45}
  conclusion: 通过率落在目标区间(20%-70%)，难度定为「中」
```

---

## 接入真实项目

当前实现的用例执行使用 `python -c` + 退出码，零依赖但表达力有限。接入真实项目时替换三处：

| 位置 | 当前实现 | 生产环境替换为 |
|---|---|---|
| `static_check.py` | 编译 + 语法解析 | `ruff` / `mypy` / `tsc` / `mvn compile` |
| `behavior_check.py` | 逐条执行 + 退出码 | 解析 `pytest --junitxml` / `go test -json` 报告 |
| `structure_check.py` | 手动传入 diff | `git diff` 自动提取 |

判分结果已支持结构化 JSON 输出，可直接接入流水线留痕。

---

## 适用场景

- AI Coding 训练数据与评测基准建设
- 模型 Coding 能力测评
- 代码生成质量门禁（适配到 CI 流程）
- 任意需要「代码是否做对了」客观判定的场景

---

## 参与贡献

欢迎提交 Issue 与 PR，尤其欢迎**误判案例**报告 —— 某个本该判 0 分的解拿了高分，或某个正确解被误拦，这类问题直接影响评测结论的可靠性。

贡献前请读 [CONTRIBUTING.md](CONTRIBUTING.md)，其中说明了判分逻辑修改的注意事项。

---

## 后续规划

- [ ] 接入 pytest / go test 报告解析，支持真实测试套件
- [ ] 判分结果可视化（得分分布、失败用例聚类）
- [ ] 难度自动校准：基于基线模型通过率自动建议题目难度
- [ ] 并行执行用例，适配大批量任务判分

---

## License

MIT License

如果这个框架对你的任务设计有帮助，欢迎 star 或提 issue 讨论。
