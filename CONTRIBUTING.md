# 贡献指南

感谢您对LLM主动提问与推理增强系统的关注！我们欢迎所有形式的贡献。

## 🤝 如何贡献

### 报告问题
- 使用 [GitHub Issues](https://github.com/your-org/llm-active-questioning/issues) 报告bug
- 请提供详细的问题描述和复现步骤
- 包含您的环境信息（Python版本、操作系统等）

### 提交功能请求
- 通过Issue描述您希望的新功能
- 解释功能的用途和价值
- 如果可能，提供设计思路或参考实现

### 代码贡献

#### 开发环境设置
```bash
# 1. Fork并克隆仓库
git clone https://github.com/your-username/llm-active-questioning.git
cd llm-active-questioning

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt
pip install -e .

# 4. 运行测试
python -m pytest tests/
```

#### 开发流程
1. **创建分支**: `git checkout -b feature/your-feature-name`
2. **开发功能**: 编写代码和测试
3. **运行测试**: 确保所有测试通过
4. **提交代码**: 使用清晰的commit信息
5. **创建PR**: 提交Pull Request

### ⚠️ 重要：数据生成工作流规则

#### 命令行使用限制
**只允许在CLI运行短校验任务（≤1分钟）：**
```bash
# ✅ 允许：基础环境和数据校验
make env-check && make sanity && make data-check
```

**严格禁止在CLI运行以下长耗时任务：**
```bash
# ❌ 禁止：任何批量生成任务
python tools/data_generator.py
make sprint-beta TARGET_ALC=100 TARGET_AR=50 TARGET_RSD=50
# ❌ 禁止：训练和评审任务
python train/ppo_runner.py
python tools/evaluate.py
# ❌ 禁止：任何 ≥10 条的生成/评审/评测任务
```

#### Notebook执行规范
**所有长任务统一在Jupyter Notebook中执行：**
```bash
# ✅ 正确方式：启动Notebook环境
jupyter notebook

# 按顺序执行：
# 1. notebooks/00_env_and_router_check.ipynb - 环境检查
# 2. notebooks/10_sprint_beta_microbatch.ipynb - 数据生成
# 3. notebooks/20_quality_reports_and_review.ipynb - 质量分析
```

#### 产物提交规则
- ✅ **允许提交**: `artifacts_review/**` 目录的全部内容
  - 审阅报告（*.md文件）
  - 抽检样本（samples/*.json，5条）
- ❌ **绝对禁止提交**: 以下目录（已在.gitignore中排除）
  - `reports/` - 生成的报告目录
  - `data/gen/` - 生成的数据文件
  - `runs/` - 运行时的中间文件和缓存
- ✅ **人工评审**: 提交5条代表性样本用于质量验证

#### 安全与合规要求
- 🔒 **隐私保护**: Notebook执行过程中不会泄露API密钥
- 🔄 **可重现性**: 所有参数在Notebook顶部配置，支持中断恢复
- 📊 **质量把关**: 自动生成质量报告，支持人工抽检验证
- 🚫 **禁止绕过**: 不得以任何形式在CLI执行长任务

#### 代码规范

##### Python代码风格
- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- 使用 `black` 进行代码格式化
- 使用 `flake8` 进行代码检查

```bash
# 格式化代码
black .

# 检查代码风格
flake8 src/ tests/
```

##### 类型提示
所有新代码都应该包含类型提示：

```python
from typing import Dict, List, Optional, Tuple

def process_dialogue(
    conversation: List[Dict[str, str]], 
    max_turns: int = 5
) -> Tuple[bool, str]:
    """处理对话流程
    
    Args:
        conversation: 对话历史
        max_turns: 最大轮次
        
    Returns:
        (是否成功, 结果消息)
    """
    pass
```

##### 文档字符串
使用Google风格的docstring：

```python
def example_function(param1: str, param2: int = 10) -> bool:
    """函数简要描述
    
    详细描述函数的功能和用法。
    
    Args:
        param1: 第一个参数的描述
        param2: 第二个参数的描述，默认值为10
        
    Returns:
        返回值的描述
        
    Raises:
        ValueError: 当参数无效时抛出
        
    Example:
        >>> result = example_function("test", 20)
        >>> print(result)
        True
    """
    pass
```

#### 测试要求

所有新功能都必须包含测试：

```python
import pytest
from src.multi_turn_system import MultiTurnInteractionSystem

def test_conversation_initialization():
    """测试对话系统初始化"""
    system = MultiTurnInteractionSystem()
    assert system is not None
    assert system.device is not None

def test_clarification_detection():
    """测试澄清需求检测"""
    system = MultiTurnInteractionSystem()
    
    # 测试需要澄清的情况
    needs_clarification, question = system.detect_clarification_need(
        "请问您指的是哪位人物？"
    )
    assert needs_clarification is True
    assert "人物" in question
    
    # 测试不需要澄清的情况
    needs_clarification, _ = system.detect_clarification_need(
        "北京是中国的首都。"
    )
    assert needs_clarification is False
```

运行测试：
```bash
# 运行所有测试
python -m pytest

# 运行特定模块测试
python -m pytest tests/test_multi_turn_system.py

# 查看测试覆盖率
python -m pytest --cov=src tests/
```

### 文档贡献

#### 改进现有文档
- 修复错别字和语法错误
- 改进代码示例
- 添加缺失的说明

#### 添加新文档
- 在 `docs/` 目录下添加Markdown文件
- 使用清晰的标题结构
- 包含代码示例和使用说明

## 📋 开发指导原则

### 代码质量
- **可读性**: 代码应该易于理解和维护
- **模块化**: 功能应该分解为小的、可重用的组件
- **错误处理**: 适当的异常处理和错误信息
- **性能**: 考虑代码的执行效率

### 设计原则
- **单一职责**: 每个函数/类应该有明确的单一职责
- **开放封闭**: 对扩展开放，对修改封闭
- **依赖注入**: 避免硬编码依赖关系
- **配置驱动**: 使用配置文件而非硬编码参数

### AI伦理
- **透明性**: 系统行为应该可解释
- **公平性**: 避免偏见和歧视
- **隐私保护**: 保护用户数据和隐私
- **安全性**: 防止恶意使用和攻击

## 🏷️ 提交信息规范

使用标准的提交信息格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Type类型：
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构代码
- `test`: 添加测试
- `chore`: 构建工具或依赖更新

#### 示例：
```
feat(multi-turn): add user interruption handling

Add support for handling user interruptions during multi-turn 
conversations. This includes detecting when users change topics
or refuse to provide clarifications.

- Add InterruptionDetector class
- Update conversation state management
- Add tests for interruption scenarios

Closes #123
```

## 🎯 优先开发方向

当前我们特别欢迎以下方面的贡献：

### 高优先级
- **强化学习训练**: PPO算法优化和训练策略
- **评估指标**: 更全面的模型性能评估体系
- **数据集扩展**: 支持更多领域的数据集
- **性能优化**: 推理速度和内存使用优化

### 中优先级
- **用户界面**: Web界面或命令行工具改进
- **部署支持**: Docker容器化和云部署
- **多语言支持**: 英文等其他语言的支持
- **可视化工具**: 对话流程和模型行为可视化

### 低优先级
- **代码重构**: 提升代码质量和可维护性
- **文档完善**: 更详细的使用指南和API文档
- **示例项目**: 更多使用场景的演示

## 🤔 需要帮助？

如果您在贡献过程中遇到任何问题：

1. 查看现有的 [Issues](https://github.com/your-org/llm-active-questioning/issues)
2. 在讨论区提问
3. 联系维护者

## 🏆 贡献者认可

我们感谢所有贡献者的努力！主要贡献者将被列在：
- README.md 的致谢部分
- 项目的贡献者页面
- 相关论文的致谢

再次感谢您的贡献！让我们一起打造更智能的AI交互系统！🚀
