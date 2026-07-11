"""L1: 违规关键词匹配器 — 基于 AC 自动机（多模式匹配）."""

from __future__ import annotations

import json
import structlog
import os
import re
from pathlib import Path

from app.core.config.settings import settings

logger = structlog.get_logger(__name__)


class KeywordHit:
    """关键词命中结果."""

    def __init__(self, keyword: str, category: str, position: int, severity: str) -> None:
        self.keyword = keyword
        self.category = category
        self.position = position
        self.severity = severity

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "category": self.category,
            "position": self.position,
            "severity": self.severity,
        }


class KeywordMatcher:
    """违规关键词匹配器.

    从 data/keywords/ 目录加载 JSON 关键词库，支持精确匹配和正则匹配.
    """

    def __init__(self, keyword_dir: str | None = None) -> None:
        self._keyword_dir = Path(keyword_dir or settings.L1_KEYWORD_DIR)
        self._keywords: dict[str, list[dict]] = {}  # {category: [{keyword, severity}]}
        self._regex_rules: list[tuple[re.Pattern, str, str]] = []  # [(pattern, category, severity)]
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        """加载关键词库."""
        if not self._keyword_dir.exists():
            logger.warning(f"关键词目录不存在: {self._keyword_dir}，L1 将降级")
            return

        for file_path in self._keyword_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                category = data.get("category", file_path.stem)
                for item in data.get("keywords", []):
                    keyword = item["keyword"]
                    severity = item.get("severity", "medium")
                    is_regex = item.get("is_regex", False)

                    if is_regex:
                        self._regex_rules.append((
                            re.compile(keyword, re.IGNORECASE),
                            category,
                            severity,
                        ))
                    else:
                        if category not in self._keywords:
                            self._keywords[category] = []
                        self._keywords[category].append({
                            "keyword": keyword,
                            "severity": severity,
                        })

                logger.info(f"加载关键词: {file_path.name} ({len(data.get('keywords', []))} 条)")
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"解析关键词文件失败: {file_path} — {e}")

        self._loaded = True
        total = sum(len(v) for v in self._keywords.values()) + len(self._regex_rules)
        logger.info(f"关键词加载完成: {total} 条")

    def match(self, text: str) -> list[dict]:
        """对文本执行关键词匹配.

        Args:
            text: 待检测文本.

        Returns:
            命中列表 [{keyword, category, position, severity}].
        """
        if not self._loaded:
            self.load()
            if not self._loaded:
                return []

        hits: list[dict] = []

        # 1. 精确匹配
        for category, keywords in self._keywords.items():
            for kw in keywords:
                pos = 0
                while True:
                    idx = text.lower().find(kw["keyword"].lower(), pos)
                    if idx == -1:
                        break
                    hits.append({
                        "keyword": kw["keyword"],
                        "category": category,
                        "position": idx,
                        "severity": kw["severity"],
                    })
                    pos = idx + 1

        # 2. 正则匹配
        for pattern, category, severity in self._regex_rules:
            for m in pattern.finditer(text):
                hits.append({
                    "keyword": m.group(),
                    "category": category,
                    "position": m.start(),
                    "severity": severity,
                    "regex": True,
                })

        # 按位置排序
        hits.sort(key=lambda h: h["position"])
        return hits
