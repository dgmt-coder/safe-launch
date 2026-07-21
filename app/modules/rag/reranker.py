"""RAG 重排序 — 混合向量相似度 + 关键词重叠的轻量级精排.

不依赖外部模型，纯本地计算，适合在 Qdrant 粗筛后做精排.
"""

from __future__ import annotations


def _bigrams(text: str) -> set[str]:
    """提取字符级 bigram 集合，中文直接按字切，英文按词."""
    # 去除标点和空白
    chars = [c for c in text if c.strip() and c not in "，。！？、；：“”‘’（）…—·"]
    if len(chars) < 2:
        return {chars[0]} if chars else set()
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def keyword_overlap_score(query: str, candidate_text: str, candidate_tags: list[str]) -> float:
    """计算查询与候选判例的关键词重叠度 (0~1).

    综合:
        - bigram 重叠率 (主要)
        - 标签命中 (加分)
    """
    q_bigrams = _bigrams(query)
    if not q_bigrams:
        return 0.0

    c_bigrams = _bigrams(candidate_text)
    # bigram Jaccard
    intersection = q_bigrams & c_bigrams
    bigram_score = len(intersection) / len(q_bigrams)

    # 标签命中加分：每个命中标签加 0.05，上限 0.15
    tag_bonus = 0.0
    for tag in candidate_tags:
        if tag in query:
            tag_bonus += 0.05
    tag_bonus = min(tag_bonus, 0.15)

    return min(bigram_score + tag_bonus, 1.0)


def hybrid_score(
    vector_similarity: float,
    keyword_score: float,
    alpha: float = 0.5,
) -> float:
    """混合得分: alpha * 向量相似度 + (1-alpha) * 关键词得分."""
    return alpha * vector_similarity + (1 - alpha) * keyword_score


def rerank(
    query: str,
    candidates: list[dict],
    *,
    alpha: float = 0.5,
) -> list[dict]:
    """对粗筛候选列表做混合精排，返回按 hybrid_score 降序的结果.

    Args:
        query: 原始查询文本.
        candidates: Qdrant 返回的候选列表，每项含 content, tags, similarity.
        alpha: 向量相似度权重 (0~1)，默认 0.5.

    Returns:
        按 hybrid_score 降序排列的候选列表，每项增加 keyword_score 和 hybrid_score 字段.
    """
    for c in candidates:
        ks = keyword_overlap_score(
            query,
            c.get("content", ""),
            c.get("tags", []),
        )
        c["keyword_score"] = round(ks, 4)
        c["hybrid_score"] = round(
            hybrid_score(c.get("similarity", 0.0), ks, alpha=alpha), 4
        )

    candidates.sort(key=lambda c: c["hybrid_score"], reverse=True)
    return candidates
