#!/usr/bin/env python3
"""
影子数据审计脚本：真伪 & 多样性 & 去模板化检测
"""

import argparse, json, re, random, statistics, sys
from collections import Counter

def mask_digits(s): return re.sub(r"\d+", "#", s.lower())
def jaccard_5gram(a,b):
  A=set([a[i:i+5] for i in range(max(0,len(a)-4))])
  B=set([b[i:i+5] for i in range(max(0,len(b)-4))])
  return (len(A&B)/len(A|B)) if A and B else 0.0

def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("infile")
  ap.add_argument("--report", default="reports/rc1/shadow_data_audit.json")
  args=ap.parse_args()
  rows=[json.loads(l) for l in open(args.infile)]
  N=len(rows)
  # 1) 真伪与字段
  assert all(r.get("source")=="hf" for r in rows), "non-HF source detected"
  assert all(r.get("task") in {"hotpotqa","strategyqa","gsm8k"} for r in rows), "illegal task"
  assert all(r.get("question") for r in rows), "empty question exists"
  # 2) 掩码唯一率 & 最频繁掩码占比
  masks=[mask_digits(r["question"]) for r in rows]
  uniq = len(set(masks))/N
  top_ratio = Counter(masks).most_common(1)[0][1]/N
  # 3) 随机 2000 对 5-gram Jaccard
  rnd=random.Random(20250821)
  sims=[]
  M=min(2000, max(0, N*(N-1)//2))
  seen=set()
  while len(sims)<M and N>1:
    i,j=rnd.randrange(N), rnd.randrange(N)
    if i==j or (i,j) in seen: continue
    seen.add((i,j))
    sims.append(jaccard_5gram(masks[i], masks[j]))
  hi = sum(1 for x in sims if x>=0.9)/max(1,len(sims))
  # 4) 长度与重复
  lens=[len(r["question"]) for r in rows]
  dup_ratio = 1 - len(set((r["task"],r["question"]) for r in rows))/N
  mean_len = statistics.mean(lens)
  stdev_len = statistics.pstdev(lens)
  # 硬门槛
  assert uniq >= 0.60, f"mask uniqueness {uniq:.2f}<0.60"
  assert top_ratio <= 0.10, f"top mask ratio {top_ratio:.2f}>0.10"
  assert hi <= 0.01, f"jaccard>=0.9 pairs {hi:.2%}>1%"
  assert 30 <= mean_len <= 300, f"mean len {mean_len:.1f} out of range"
  assert stdev_len >= 15, f"std len {stdev_len:.1f}<15"
  assert dup_ratio <= 0.01, f"dup ratio {dup_ratio:.2%}>1%"
  rep=dict(N=N, mask_uniqueness=uniq, top_mask_ratio=top_ratio, jaccard_hi_ratio=hi,
           mean_len=mean_len, std_len=stdev_len, dup_ratio=dup_ratio)
  import os; os.makedirs("reports/rc1", exist_ok=True)
  json.dump(rep, open(args.report,"w"), indent=2)
  print("AUDIT OK:", rep)

if __name__=="__main__":
  main()
