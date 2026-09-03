"""Text chunking strategies.

chunking 策略是决定 RAG 检索质量的关键，比选哪个向量库重要得多。

P3 实现：滑动窗口 + 句子边界对齐
  - chunk_size：目标 token 数（用字符数近似，中文 1 字≈1 token）
  - overlap：相邻 chunk 重叠字符数，保证跨 chunk 上下文不丢失
  - 在句号/换行处对齐，避免在句子中间截断
"""

from __future__ import annotations

import re

# 句子结束符（中英文混合）
_SENT_END = re.compile(r"[。！？\.\!\?]\s*")

CHUNK_SIZE = 600    # chars (~300-400 tokens for Chinese)
CHUNK_OVERLAP = 80  # chars


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks, aligned to sentence boundaries where possible.
    Returns list of chunk strings.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk = text[start:]
            if chunk.strip():
                chunks.append(chunk.strip())
            break

        # Try to align end to a sentence boundary within ±100 chars
        search_start = max(start, end - 100)
        search_end = min(len(text), end + 100)
        segment = text[search_start:search_end]

        m = None
        for m in _SENT_END.finditer(segment):
            pass  # find last match in segment

        if m:
            end = search_start + m.end()

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Next chunk starts with overlap
        start = end - overlap
        if start <= 0:
            start = end  # prevent infinite loop

    return chunks


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1 token per Chinese char, ~0.75 per ASCII char."""
    chinese = sum(1 for c in text if "一" <= c <= "鿿")
    ascii_chars = len(text) - chinese
    return chinese + int(ascii_chars * 0.75)
