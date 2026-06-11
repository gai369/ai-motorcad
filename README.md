# AI Motor Design Assistant

> 电机电磁设计 AI 副驾驶 - 读懂你的设计、分析问题、给出建议、你来决策

## 核心理念

不需要大量训练数据。AI 内置电磁学理论和电机设计经验，通过规则引擎 + LLM 推理来辅助你的设计工作：

| 能力 | 说明 |
|---|---|
| 连接 Motor-CAD | 通过 pymotorcad 读取设计参数、运行仿真 |
| 自动分析 | 对比设计规则，诊断磁密、转矩脉动、温升等问题 |
| 智能建议 | 基于电磁学原理给出可操作的改进方案 |
| 生成报告 | 自动输出 Markdown 设计评审报告 |

## 快速开始

### 安装依赖

```bash
pip install ansys-pymotorcad
```

### 使用 CLI

```bash
# 连接到已打开的 Motor-CAD
python -m ai_motorcad.cli connect

# 分析当前设计
python -m ai_motorcad.cli analyze

# 获取改进建议
python -m ai_motorcad.cli suggest

# 生成设计评审报告
python -m ai_motorcad.cli report "my_motor_design" -o review.md
```

### 在 Python 中使用

```python
from ai_motorcad.connector import MotorCADConnector
from ai_motorcad.analyzer import MotorAnalyzer
from ai_motorcad.advisor import MotorAdvisor
from ai_motorcad.reporter import DesignReporter

# 连接 Motor-CAD
mc = MotorCADConnector()
mc.connect()

# 获取设计状态
state = mc.get_full_state()

# 分析
analyzer = MotorAnalyzer()
report = analyzer.analyze(state)
print(report.summary)

# 获取建议
advisor = MotorAdvisor()
suggestions = advisor.suggest(report, state)
for s in suggestions:
    print(f"[P{s.priority}] {s.title}")

# 生成报告
reporter = DesignReporter()
md = reporter.generate_markdown(report, suggestions, "My Design", state)
reporter.save_report(md, "design_review.md")
```

### 离线 Demo

```bash
python examples/demo_analysis.py
```

## 架构

```
ai_motorcad/
├── __init__.py      # 包入口
├── connector.py     # Motor-CAD 连接封装 (pymotorcad)
├── knowledge.py     # 电磁设计知识库 (规则、经验、材料数据)
├── analyzer.py      # 仿真结果分析引擎
├── advisor.py       # 改进建议生成引擎
├── reporter.py      # Markdown 报告生成器
└── cli.py           # 命令行交互界面
examples/
└── demo_analysis.py # 离线分析示例
```

## 分析能力

- **电磁检查**: 气隙磁密、齿轭磁密、转矩脉动、齿槽转矩、效率、电流密度
- **热检查**: 绕组最高温度、永磁体温度
- **机械检查**: 转子线速度
- **建议类型**: 几何优化、绕组设计、材料选型、冷却方案、控制策略

## 依赖

- Python 3.8+
- pymotorcad (ansys-pymotorcad) - 需要 ANSYS Motor-CAD 许可证