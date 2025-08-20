# RC1 安全启动指南

## 🔐 总架构师熔断状态确认

**当前状态**: ⛔ **训练完全熔断** - 防止无授权启动

### 强制闸门列表
1. ✅ **train/ppo_runner.py** 硬闸门就位
2. ✅ **单一提供商强制** (Gemini/DeepSeek择一)
3. ✅ **评分凭证日志** 实时记录
4. ✅ **影子评估阈值** 预跑门槛卡死
5. ✅ **自动Round2检查** 禁止手工pass

## 🎯 三种启动方式

### 方式A: 本地环境（推荐起步）

1. **配置API Key**:
   ```bash
   # 创建 .env 文件（不会进git）
   cat > .env << EOF
   RUN_MODE=prod
   SCORER_PROVIDER=gemini
   GEMINI_API_KEY=AIzaSyBLECdu94qJWPFOZ--9dIKpeWaWjSGJ_z0
   EOF
   ```

2. **验证连通性**:
   ```bash
   source scripts/load_env.sh
   python scripts/probe_scorer.py --n 6 --provider gemini --live
   python scripts/assert_not_simulated.py --cache_hit_lt 0.90
   ```

3. **数据质量修复**:
   ```bash
   ./scripts/force_rebuild_seed_pool.sh
   ```

4. **双轮预检**:
   ```bash
   python scripts/auto_round2_check.py
   ```

5. **等待PM授权**:
   ```bash
   # 只有PM/总架构师可以创建此文件
   # touch reports/preflight/RC1_GO
   ```

### 方式B: Google Colab（算力友好）

1. **打开笔记本**: `colab/rc1_colab.ipynb`
2. **配置Secrets**: 左侧🔑面板添加 `GEMINI_API_KEY`
3. **选择GPU运行时**: T4/L4/A100
4. **一键执行**: 按顺序运行所有单元格

### 方式C: 云平台（长训练）

#### RunPod (按秒计费)
```bash
# 停机=停计费，适合间歇训练
# 选择 PyTorch 2.1+ 镜像
git clone https://github.com/Atomheart-Father/llm-active-questioning.git
cd llm-active-questioning
# 按方式A流程执行
```

#### Paperspace (按小时计费)
```bash
# 类似RunPod，关机后只收存储费
# 选择 ML-in-a-Box 模板
```

## 📊 成本预估

| 环境 | 短期验证 | 完整训练 | 优势 |
|------|----------|----------|------|
| **Colab** | $10-20 | $50-100 | 即开即用，CU按需 |
| **RunPod** | $5-15 | $30-80 | 按秒计费，灵活 |
| **Paperspace** | $8-20 | $40-120 | 简单配置 |
| **AWS EC2** | $10-25 | $50-150 | 稳定可靠 |

## 🚨 安全检查点

### ✅ 必须通过的门槛

**Round 1 (严格模式)**:
- [ ] Gemini API Key有效性验证
- [ ] `probe_scorer` billable_count≥1
- [ ] `assert_not_simulated --cache_hit_lt 0.90` PASS
- [ ] 种子池多样性: distinct-2≥0.60, 角色≥4, 语体≥3
- [ ] 难度分布: Hard≥30%, Easy≤30%

**Round 2 (放宽模式)**:
- [ ] `assert_not_simulated --cache_hit_lt 0.95` PASS
- [ ] 影子评估: Spearman≥0.55, Top10重合≥0.60
- [ ] 自动生成 `round2_pass.json`

**最终解锁**:
- [ ] PM/总架构师创建 `reports/preflight/RC1_GO`

### ❌ 会被拦截的情况

1. **无真实API Key** → 探针失败
2. **缓存命中率过高** → 反模拟检查失败
3. **数据质量不达标** → 种子池验证失败
4. **影子指标过低** → Round2检查失败
5. **缺少授权文件** → 训练启动被拒绝

## 🔧 故障排除

### Gemini API问题
```bash
# 检查配额
curl -H "x-goog-api-key: $GEMINI_API_KEY" \
  "https://generativelanguage.googleapis.com/v1beta/models"

# 升级到付费层
# 访问 https://ai.google.dev/ → Enable billing
```

### 数据质量问题
```bash
# 强制重建（多样性增强）
./scripts/force_rebuild_seed_pool.sh

# 检查具体指标
python scripts/validate_pool.py data/rollouts/rc1_seed.jsonl --verbose
```

### 影子指标过低
```bash
# 重新校准权重
python -m src.evaluation.weight_calib --config configs/weights.json

# 检查成功标签定义
python -c "from src.evaluation.shadow_run import success; print(success.__doc__)"
```

## 📞 支持联系

- **总架构师**: 负责最终 RC1_GO 授权
- **GitHub Issues**: 技术问题报告
- **文档**: `docs/` 目录完整说明

---

**⚠️ 重要提醒**: 
- 本地算力不足时优先使用 Colab
- 长训练再考虑按秒计费的云平台
- 所有API Key通过安全方式注入，绝不暴露在代码中
