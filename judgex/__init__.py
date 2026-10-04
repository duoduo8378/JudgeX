"""JudgeX · AI Coding 任务三层判分框架。

把主观的代码质量判断，转成可自动执行的断言。

三层设计：
  静态层 (Static)    —— 代码能否构建、语法是否正确    一票否决
  结构层 (Structure) —— 实现方式是否符合约束          一票否决
  动态层 (Behavior)  —— 行为是否正确                  比例给分，权重 80

详见 README.md 与 docs/design.md。
"""

from .judge import Judge, TaskConfig, JudgeReport

__version__ = "0.1.0"
__all__ = ["Judge", "TaskConfig", "JudgeReport"]
