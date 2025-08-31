#!/usr/bin/env python3
"""
权重加载器 - 向后兼容 + 严格校验
"""

import json, warnings
from .exceptions import WeightsSchemaError

ALIASES = {"rules_score":"rules"}
ALLOWED = {"logic_rigor","question_quality","reasoning_completeness","natural_interaction","rules"}

def load_weights(path="configs/weights.json"):
    d = json.load(open(path))
    if "weights" in d and isinstance(d["weights"], dict):
        d = d["weights"]
    # alias 映射 + 合并
    fixed = {}
    for k,v in d.items():
        k2 = ALIASES.get(k, k)
        if k != k2: warnings.warn(f"weights key '{k}' is deprecated, use '{k2}'", DeprecationWarning)
        if k2 in ALLOWED:
            fixed[k2] = fixed.get(k2, 0.0) + float(v)
    # 归一化 + 非负
    s = sum(max(0.0,float(x)) for x in fixed.values())
    if s <= 0: raise WeightsSchemaError("weights sum <= 0")
    fixed = {k: max(0.0,float(v))/s for k,v in fixed.items()}
    # 全字段存在性（可选：允许缺失则按0处理）
    missing = ALLOWED - fixed.keys()
    if missing: raise WeightsSchemaError(f"missing keys: {sorted(missing)}")
    return fixed
