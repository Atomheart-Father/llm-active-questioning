#!/usr/bin/env python3
"""
从Hugging Face数据集重建影子集，确保真实数据源与溯源信息
"""

import argparse, json, random, os
from datasets import load_dataset

ALLOWED = {
  "hotpotqa": dict(ds="hotpot_qa", config="distractor", split="validation",
                   map=lambda r: (r["question"], r["answer"])),
  "strategyqa": dict(ds="strategy_qa", split="train",
                     map=lambda r: (r["question"], "yes" if bool(r["answer"]) else "no")),
  "gsm8k": dict(ds="gsm8k", config="main", split="train",
                map=lambda r: (r["question"], str(r["answer"]).strip())),
}

def take(ds_name, n, seed):
  cfg = ALLOWED[ds_name]
  name = cfg.get("config")
  d = load_dataset(cfg["ds"], name, split=cfg["split"])
  idx = list(range(len(d)))
  random.Random(seed).shuffle(idx)
  out=[]
  for k,i in enumerate(idx[:n]):
    q, a = cfg["map"](d[i])
    out.append(dict(
      id=f"{ds_name}_{k}",
      task=ds_name,
      question=str(q).strip(),
      answer=str(a).strip(),
      source="hf",
      hf_dataset=cfg["ds"],
      hf_config=name,
      hf_split=cfg["split"],
      hf_fingerprint=getattr(d, "_fingerprint", None),
      hf_num_rows=len(d),
    ))
  return out

def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--n", type=int, default=245)
  ap.add_argument("--seed", type=int, default=20250821)
  ap.add_argument("--out", default="data/shadow_eval_245.jsonl")
  ap.add_argument("--manifest", default="reports/rc1/sample_manifest.json")
  args=ap.parse_args()
  n1=args.n//3; n2=args.n//3; n3=args.n-n1-n2
  hot=take("hotpotqa", n1, args.seed+1)
  sqa=take("strategyqa", n2, args.seed+2)
  gsm=take("gsm8k", n3, args.seed+3)
  all_s=hot+sqa+gsm
  os.makedirs(os.path.dirname(args.out), exist_ok=True)
  with open(args.out,"w") as f:
    for r in all_s: f.write(json.dumps(r, ensure_ascii=False)+"\n")
  manifest=dict(samples=[{"id":s["id"],"task":s["task"],"question":s["question"]} for s in all_s])
  os.makedirs(os.path.dirname(args.manifest), exist_ok=True)
  json.dump(manifest, open(args.manifest,"w"), indent=2, ensure_ascii=False)
  print("OK rebuild:", len(all_s), "->", args.out, args.manifest)

if __name__=="__main__":
  main()
