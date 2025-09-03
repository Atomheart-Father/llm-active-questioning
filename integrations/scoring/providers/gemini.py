# src/scoring/providers/gemini.py
import os, time, json, re
import google.generativeai as genai

NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)")

def _to_float01(x):
    """把多种评分标尺统一到 [0,1]。"""
    if x is None: return None
    try:
        v = float(x)
    except Exception:
        return None
    # 兼容 0-1、0-10、0-100 等标尺
    if v <= 1.0 and v >= 0.0: return v
    if 0.0 <= v <= 10.0: return max(0.0, min(1.0, v/10.0))
    if 0.0 <= v <= 100.0: return max(0.0, min(1.0, v/100.0))
    # 其他情况直接裁剪
    return max(0.0, min(1.0, v))

def _extract_score_from_text(txt: str):
    # 优先找 JSON
    try:
        obj = json.loads(txt)
        for k in ("score","scores","rating","value"):
            if k in obj:
                if isinstance(obj[k], (list,tuple)) and obj[k]:
                    return _to_float01(obj[k][0])
                return _to_float01(obj[k])
    except Exception:
        pass
    # 退化：找第一个数字
    m = NUM_RE.search(txt or "")
    return _to_float01(m.group(1)) if m else None

def score(prompt: str, model: str = None, require_live=True):
    """返回 dict: {score:float in [0,1], latency_ms:int, usage:{...}, raw:str}"""
    # 强制 live：禁用任何你自家的缓存通道
    if require_live and os.getenv("SCORING_CACHE_DISABLE","") != "1":
        os.environ["SCORING_CACHE_DISABLE"] = "1"

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    mdl = model or os.getenv("GEMINI_MODEL","gemini-2.5-flash")
    # 注入 nonce，抵消上游/代理层的重复请求缓存
    prompt_live = prompt + f"\n\nnonce:{time.time_ns()}"
    
    # 添加严格评分标准
    rubric = """
You are a strict judge. Evaluate the model's answer ONLY for the following criteria, weighted:
- Correctness (0.55)
- Reasoning Quality (0.25)
- Brevity/Clarity (0.10)
- Unnecessary Clarification Penalty (0.10; subtract if it asks redundant questions without need)
Return a pure JSON: {"score": <0..1>} with 2 decimals.
Calibration anchors:
- 0.15 = wrong or vacuous
- 0.35 = partially correct with major gaps
- 0.55 = mostly correct but shallow/wordy
- 0.75 = correct with acceptable reasoning
- 0.90 = correct and strong reasoning, concise
"""
    
    cfg = {"temperature": 0, "response_mime_type": "application/json"}
    t0 = time.time()
    resp = genai.GenerativeModel(mdl).generate_content(prompt_live + "\n\n" + rubric, generation_config=cfg)
    dt = int((time.time()-t0)*1000)

    # usage 兼容提取
    um = getattr(resp, "usage_metadata", None)
    usage = dict(
        prompt_tokens = getattr(um,"prompt_token_count", None) if um else None,
        completion_tokens = getattr(um,"candidates_token_count", None) if um else None,
        total_tokens = getattr(um,"total_token_count", None) if um else None,
    )

    # 文本/部件收集
    text = resp.text if hasattr(resp,"text") else None
    parts = []
    if getattr(resp,"candidates",None):
        for c in resp.candidates:
            if getattr(c,"content",None) and getattr(c.content,"parts",None):
                for p in c.content.parts:
                    if hasattr(p,"text"):
                        parts.append(p.text)

    # 解析评分
    score = None
    if text: score = _extract_score_from_text(text)
    if score is None:
        for p in parts:
            score = _extract_score_from_text(p)
            if score is not None: break

    raw_preview = (text or (parts[0] if parts else ""))[:500]
    if score is None:
        raise AssertionError(f"Gemini response parse failed; raw preview: {raw_preview!r}")

    return dict(score=score, latency_ms=dt, usage=usage, raw=raw_preview)
