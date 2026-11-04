"""
答案忠实度：一句一句看回答有没有原样出现在检索片段里。

不足 4 个字的碎片不记分。没有可记分的句子时返回 applicable=False，
调用方不要把这种情况算成 0 分。这里不调用模型。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_CLAIM_SPLIT = re.compile(r"[。！？!?；;\n]+")
_MIN_CLAIM_CHARS = 4


def score_faithfulness(answer: str, contexts: Optional[List[str]] = None) -> Dict[str, Any]:
    claims = _claims(answer)
    if not claims:
        return {"applicable": False, "score": None, "grounded": 0, "claims": 0}

    blob = _compact("".join(contexts or []))
    grounded = sum(1 for claim in claims if claim in blob)
    return {
        "applicable": True,
        "score": grounded / len(claims),
        "grounded": grounded,
        "claims": len(claims),
    }


def _claims(answer: str) -> List[str]:
    claims = []
    for piece in _CLAIM_SPLIT.split(answer or ""):
        compact = _compact(piece)
        if len(compact) >= _MIN_CLAIM_CHARS:
            claims.append(compact)
    return claims


def _compact(text: str) -> str:
    return "".join((text or "").split())
