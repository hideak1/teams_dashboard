"""Token estimation from text length.

No official per-agent token API exists, so we approximate:
  - English text: len(text) / 4
  - CJK text: len(text) / 2
  - Mixed: weighted average based on CJK character ratio

UI should always display with ≈ prefix.
"""

import re

_CJK_PATTERN = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef"
    r"\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)


def estimate_tokens(text: str) -> int:
    """Estimate token count from text content."""
    if not text:
        return 0
    total = len(text)
    cjk_count = len(_CJK_PATTERN.findall(text))
    if total == 0:
        return 0
    cjk_ratio = cjk_count / total
    # Weighted divisor: 2 for CJK, 4 for English
    divisor = 2 * cjk_ratio + 4 * (1 - cjk_ratio)
    return max(1, int(total / divisor))


def estimate_cost(tokens: int, model: str = "sonnet") -> float:
    """Estimate USD cost. Very rough approximation.

    Prices per 1M tokens (input+output averaged):
      Sonnet: ~$6/M
      Opus: ~$30/M
    """
    per_million = {"sonnet": 6.0, "opus": 30.0, "haiku": 1.0}
    rate = per_million.get(model, 6.0)
    return tokens * rate / 1_000_000
