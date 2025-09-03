# 环境配置说明

## Sprint-α 硬闸门系统环境配置

### 创建 .env 文件

1. 复制模板：
   ```bash
   cp .env.template .env
   ```

2. 编辑 `.env` 文件，填入实际值

### 必需环境变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `GEMINI_API_KEY` | Gemini API 主要密钥 | `AIzaSyD...` |
| `GEMINI_API_KEY2` | Gemini API 备用密钥 | `AIzaSyD...` |
| `GEMINI_API_KEY3` | Gemini API 第三备用密钥 | `AIzaSyD...` |
| `DeepSeek_API_KEY` | DeepSeek API 密钥 | `sk-...` |
| `HF_TOKEN` | HuggingFace 访问令牌 | `hf_...` |
| `GIT_TOKEN` | GitHub 个人访问令牌 | `ghp_...` |
| `GITHUB_REPO` | GitHub 仓库标识 | `Atomheart-Father/llm-active-questioning` |
| `HF_REPO_ID` | HuggingFace 仓库标识 | `Atomheart-Father/rc1-qwen3-4b-thinking-gemini` |
| `MODEL_NAME` | 模型名称 | `Qwen/Qwen3-4B-Thinking-2507` |

### 可选环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `THOUGHT_IN_HISTORY` | `false` | 是否在对话历史中保留 `<think>` 标签 |
| `DATASET_MIN_SAMPLES` | `8` | 数据集最小样本数阈值 |

### 获取 API 密钥

#### Gemini API Key
1. 访问 [Google AI Studio](https://aistudio.google.com/)
2. 创建新项目或选择现有项目
3. 导航到 "API Keys" 部分
4. 创建新的 API Key
5. 复制密钥并添加到 `.env` 文件

#### DeepSeek API Key
1. 访问 [DeepSeek 平台](https://platform.deepseek.com/)
2. 注册账户并登录
3. 在控制台中创建 API Key
4. 复制密钥并添加到 `.env` 文件

#### HuggingFace Token
1. 访问 [HuggingFace](https://huggingface.co/)
2. 登录账户
3. 进入 Settings > Access Tokens
4. 创建新的 Token（选择 "Read" 权限）
5. 复制 Token 并添加到 `.env` 文件

#### GitHub Token
1. 访问 GitHub Settings > Developer settings > Personal access tokens
2. 生成新的 Token（选择 "repo" 权限）
3. 复制 Token 并添加到 `.env` 文件

### 安全注意事项

- ✅ **不要**将 `.env` 文件提交到版本控制系统
- ✅ **不要**与任何人分享 `.env` 文件内容
- ✅ **定期轮换** API 密钥
- ✅ 使用**最小权限原则**创建令牌

### 测试配置

运行环境检查验证配置：

```bash
make env-check
```

如果所有变量都正确配置，你会看到：

```
🔍 开始环境变量合规检查...
✅ 所有必需环境变量都存在
📝 报告已保存至: reports/env_check.md
✅ 环境检查通过
```

### 故障排除

#### "环境变量缺失" 错误
- 检查 `.env` 文件是否存在
- 确认变量名拼写正确
- 确保等号前后没有空格
- 检查变量值不为空

#### "API 密钥无效" 错误
- 验证密钥格式是否正确
- 检查密钥是否过期
- 确认账户有相应权限
- 测试 API 连通性

### 示例 .env 文件

```bash
# Gemini API 配置
GEMINI_API_KEY=AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY2=AIzaSyDyyyyyyyyyyyyyyyyyyyyyyyyy
GEMINI_API_KEY3=AIzaSyDzzzzzzzzzzzzzzzzzzzzzzzzz

# DeepSeek API 配置
DeepSeek_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# HuggingFace 配置
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# GitHub 配置
GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=Atomheart-Father/llm-active-questioning

# HuggingFace 仓库配置
HF_REPO_ID=Atomheart-Father/rc1-qwen3-4b-thinking-gemini

# 模型配置
MODEL_NAME=Qwen/Qwen3-4B-Thinking-2507

# 可选配置
THOUGHT_IN_HISTORY=false
DATASET_MIN_SAMPLES=8
```
