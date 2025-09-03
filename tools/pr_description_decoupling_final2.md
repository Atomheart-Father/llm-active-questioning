# hotfix/decoupling-final2: purge root, fix README, enforce root guard

## 🔥 PR 概述

这是一个**最终的强制清理PR**，彻底解决主分支的Gemini残留问题，确保"主回路离线可复现，Gemini仅Sidecar"的架构原则100%落地。

## 🎯 问题根因分析

尽管PR #25和#26已合并，但主分支仍存在：

1. **根目录架构污染**: 仓库主页仍显示`gemini_cache.sqlite`、`gemini_integration.py`
2. **README文档不一致**: 仍指引旧的根路径用法
3. **CI守护不充分**: 需要更强的根目录污染检测

## ✅ 修复成果

### 1. **根目录强制清理** 🧹

**确保根目录100%净空**:
- ✅ **清理缓存文件**: `git rm --cached gemini_cache.sqlite`
- ✅ **迁移集成脚本**: 确认`integrations/gemini/gemini_integration.py`存在
- ✅ **gitignore强化**: 添加`gemini_*.sqlite`规则防止未来污染

### 2. **README强制更正** 📖

**确保文档指引100%正确**:
- ✅ **路径统一**: 所有`python gemini_integration.py` → `python integrations/gemini/gemini_integration.py`
- ✅ **角色明确**: 标注"Sidecar工具，不进入训练主回路"
- ✅ **一致性**: 文档与代码完全对齐

### 3. **CI根目录守护增强** 🔒

**新增专用根目录守护步骤**:
```yaml
- name: Root directory must be clean
  run: |
    echo "🔍 检查根目录是否干净..."
    if ls -1 | egrep -q "^(gemini_cache\.sqlite|gemini_integration\.py)$"; then
      echo "❌ 根目录被Gemini文件污染"
      ls -la | egrep "gemini_cache\.sqlite|gemini_integration\.py" || true
      exit 1
    else
      echo "✅ 根目录干净，无Gemini残留"
    fi
```

## 🚀 预期效果

本次强制清理后：
- ✅ **仓库主页干净**: 根目录无任何Gemini文件
- ✅ **文档指引正确**: README指向正确Sidecar路径
- ✅ **CI守护强化**: 双重检测确保根目录永不污染
- ✅ **架构原则落地**: "主回路离线可复现，Gemini仅Sidecar"

## 📊 自检验证结果

```
=== 最终自检验证 ===
1. 根目录净空检查:
no root gemini files ✅

2. Sidecar存在检查:
sidecar present ✅

3. README路径检查:
100:python integrations/gemini/gemini_integration.py
README path ok ✅
```

## 🎯 验收标准 (DoD)

- ✅ **仓库主页**: 根目录不再出现`gemini_cache.sqlite`、`gemini_integration.py`
- ✅ **README**: 所有运行示例改为`integrations/gemini/`路径
- ✅ **CI检查**: 具备精确扫描 + 根目录守护双重保护
- ✅ **门禁**: All checks have passed (包含新的root guard)

## 📞 技术细节

* **修复类型**: 🔥 强制清理热修复 (Hotfix)
* **影响范围**: 根目录清理 + 文档修正 + CI守护增强
* **风险等级**: 极低 (只清理污染文件和强化检测)
* **验证方式**: 三重自检验证 + CI双重守护

## 🔗 创建PR

**请在GitHub上创建PR:**

1. 访问: https://github.com/Atomheart-Father/llm-active-questioning/compare/hotfix/decoupling-final2
2. 标题: `hotfix/decoupling-final2: purge root, fix README, enforce root guard`
3. 基准分支: `main`
4. 描述: 复制本文件内容

---

**紧急程度**: 🔥 高优先级
**提交者**: Cursor AI Assistant
**分支**: `hotfix/decoupling-final2`
**关联**: 强制清理 - 解决主分支根目录残留和README不一致问题
