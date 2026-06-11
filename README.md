# AI Motor Design Assistant

> 电机电磁设计 AI 副驾驶 - 自然语言对话驱动设计全流程

## 核心理念

不需要大量训练数据。AI 内置电磁学理论和电机设计经验，用**对话**的方式辅助设计：

```
你: "我有一个150kW、4000rpm、IPM、水冷的项目"
AI:  分析指标 -> 生成初版方案 (几何/磁钢/绕组/材料)
你:  在 Motor-CAD 建模，手动跑仿真
你:  "仿真跑完了，记录结果"
AI:  读取数据 -> 对比指标 -> 指出差距 -> 给出具体修改建议
你:  "磁钢厚度改成6.5mm"
AI:  修改参数 + 提示耦合影响 + 记录变更
你:  检查 -> 跑仿真 -> 循环...
```

## 快速开始

### 安装

```bash
pip install ansys-pymotorcad  # 可选，离线模式无需此依赖
```

### 对话模式

```bash
# 启动交互式对话
python -m ai_motorcad.chat

# 或直接加载指标文件
python -m ai_motorcad.chat examples/sample_spec.yaml
```

### 离线 Demo

```bash
python examples/chat_demo.py
```

### 代码调用

```python
from ai_motorcad.chat import MotorCADChat

chat = MotorCADChat()
chat.run()  # 启动交互对话
```

## 命令一览

| 命令 | 说明 |
|---|---|
| `sample_spec.yaml` | 加载指标文件 (JSON/YAML/TXT) |
| `spec: 150kW IPM 水冷...` | 自然语言描述指标 |
| `generate` | 生成初版方案 |
| `磁钢厚度 6.5` | 修改参数（中英文均可） |
| `齿宽 +1` | 相对修改 |
| `record` | 记录仿真结果 |
| `compare` | 对比项目指标 |
| `suggest` | 获取改进建议 |
| `show` | 查看当前方案 |
| `history` | 查看变更记录 |
| `undo` | 撤销上一步 |
| `report` | 生成设计评审报告 |
| `save / load` | 保存/恢复会话 |

## 架构

```
ai_motorcad/
├── __init__.py        # 包入口
├── knowledge.py       # 电磁设计知识库
├── connector.py       # Motor-CAD 连接 (双模式: 在线/离线)
├── design_spec.py     # 指标解析 + 初版方案生成
├── design_tracker.py  # 会话追踪 + 指标对比
├── analyzer.py        # 仿真结果分析引擎
├── advisor.py         # 改进建议引擎
├── chat.py            # 对话主程序 (30+命令)
├── reporter.py        # Markdown 报告生成
└── cli.py             # 命令行工具
examples/
├── sample_spec.yaml   # 示例指标文件
├── chat_demo.py       # 离线对话 Demo
└── demo_analysis.py   # 分析功能 Demo
pymotorcad/            # ANSYS pymotorcad 源码 (本地引用)
```

## 能力矩阵

| 功能 | 离线模式 | 在线模式 |
|---|---|---|
| 指标文件加载 | YES | YES |
| 初版方案生成 | YES | YES |
| 参数修改 (中/英) | YES (记录) | YES (直接改Motor-CAD) |
| 耦合警告提示 | YES | YES |
| 仿真结果记录 | YES (手动输入) | YES (自动读取) |
| 指标对比 | YES | YES |
| 主动建议 (含量化预期) | YES | YES |
| 设计报告生成 | YES | YES |
| 会话保存/恢复 | YES | YES |

## 依赖

- Python 3.8+
- pymotorcad (可选，在线模式需要 ANSYS Motor-CAD 许可证)
