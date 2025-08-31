#!/usr/bin/env python3
"""
权重键名迁移脚本 - 将历史别名映射为标准键名
"""

import json, sys, pathlib

ALIASES = {
    "rules_score": "rules",
    # 如有其它历史别名，继续在此登记
}
ALLOWED = {"logic_rigor","question_quality","reasoning_completeness","natural_interaction","rules"}

def load(path):
    d = json.load(open(path))
    # 容错：有人把权重包在 "weights" 里
    if isinstance(d, dict) and "weights" in d and isinstance(d["weights"], dict):
        d = d["weights"]
    return d

def normalize(w):
    total = sum(max(0.0, float(v)) for v in w.values())
    if total == 0: raise ValueError("all-zero weights")
    return {k: max(0.0, float(v))/total for k,v in w.items()}

def migrate(w):
    ww = {}
    for k,v in w.items():
        k2 = ALIASES.get(k, k)
        ww[k2] = ww.get(k2, 0.0) + float(v)
    # 仅保留允许字段
    ww = {k:v for k,v in ww.items() if k in ALLOWED}
    return normalize(ww)

def main(p="configs/weights.json", out="configs/weights.json"):
    w0 = load(p)
    w1 = migrate(w0)
    json.dump(w1, open(out, "w"), indent=2, ensure_ascii=False)
    pathlib.Path("artifacts").mkdir(exist_ok=True, parents=True)
    json.dump({"before": w0, "after": w1}, open("artifacts/weights.migration.audit.json","w"), indent=2, ensure_ascii=False)
    print("OK ->", out)

if __name__ == "__main__":
    main(*sys.argv[1:])
