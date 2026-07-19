"""L3: DeepSeek LLM 深度语义判定器 — 支持判例 Few-Shot 注入."""

from __future__ import annotations

import json
import structlog
import time
from typing import Any

import httpx

from app.core.config.settings import settings
from app.schemas.rag import PrecedentHit

logger = structlog.get_logger(__name__)

# ── System Prompt ────────────────────────────────────────────────
SYSTEM_PROMPT = """你是一个专业的游戏内容安全审核助手。你的任务是对用户提交的游戏相关内容进行合规性审核。

审核维度包括：
1. 法律法规红线：政治敏感、色情、暴力、赌博、毒品等
2. 游戏基本原则：健康向上、社会主义核心价值观
3. 游戏内合规要求：版号、实名认证、防沉迷等

你必须严格以JSON格式返回审核结果，格式如下：
{
  "is_violation": true/false,
  "violation_type": "political" | "pornographic" | "violence" | "gambling" | "drugs" | "fraud" | "other" | null,
  "confidence": 0.0~1.0,
  "reasoning": "判定理由，简短说明",
  "relevant_regulations": ["相关法规条款"]
}

注意：
- 不确定时倾向于标记为合规（is_violation=false）
- confidence 反映你对判定结果的确信程度
- 只返回JSON，不要包含其他文字"""

# ── Few-Shot Message 模板 ────────────────────────────────────────

_FEWSHOT_PREAMBLE = (
    "以下是与待审核内容**最相似的已人工确认判例**，请参考这些判例的判定标准和尺度，"
    "对最后一条内容做出判定：\n\n"
)

_PRECEDENT_TEMPLATE = (
    "【判例 {index}】相似度: {similarity:.0%}\n"
    "内容: {content}\n"
    "人工判定: {verdict} ({violation_type})\n"
    "理由: {reasoning}\n"
)

_REVIEW_TEMPLATE = "\n---\n待审核内容:\n{content}"


class DeepSeekAnalyzer:
    """DeepSeek LLM 审核判定器 — 支持判例 few-shot 注入."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    @property
    def is_available(self) -> bool:
        return bool(settings.DEEPSEEK_API_KEY)

    async def analyze(
        self,
        content: str,
        *,
        precedents: list[PrecedentHit] | None = None,
        review_dimension: str | None = None,
    ) -> dict[str, Any]:
        """调用 DeepSeek 进行深度语义审核.

        Args:
            content: 待审核文本.
            precedents: 可选，RAG 检索到的相似判例列表，用于 few-shot.
            review_dimension: 可选，审核维度（用于日志）.

        Returns:
            结构化判定结果.
        """
        if not self.is_available:
            raise RuntimeError("DeepSeek API Key 未配置")

        if not content or not content.strip():
            raise ValueError("审核内容不能为空")

        messages = self._build_messages(content, precedents)
        client = self._client
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(settings.DEEPSEEK_TIMEOUT))

        try:
            t0 = time.perf_counter()
            response = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 1024,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            elapsed = time.perf_counter() - t0
            body = response.json()
            raw = body["choices"][0]["message"]["content"]
            result = json.loads(raw)
            result["_llm_model"] = settings.DEEPSEEK_MODEL
            result["_llm_time_ms"] = int(elapsed * 1000)
            if precedents:
                result["_precedent_count"] = len(precedents)
            if review_dimension:
                result["_review_dimension"] = review_dimension
            return result

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"DeepSeek 返回解析失败: {e}")
            return {
                "is_violation": None,
                "violation_type": None,
                "confidence": 0.0,
                "reasoning": f"LLM 返回解析失败: {e}",
                "error": "parse_error",
            }
        except httpx.TimeoutException:
            logger.error("DeepSeek API 超时")
            return {
                "is_violation": None,
                "violation_type": None,
                "confidence": 0.0,
                "reasoning": "LLM 调用超时",
                "error": "timeout",
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"DeepSeek API 错误: {e.response.status_code}")
            return {
                "is_violation": None,
                "violation_type": None,
                "confidence": 0.0,
                "reasoning": f"LLM API 错误: {e.response.status_code}",
                "error": "api_error",
            }

    @staticmethod
    def _build_messages(
        content: str, precedents: list[PrecedentHit] | None
    ) -> list[dict[str, str]]:
        """构造消息列表 — 有判例时自动组装 few-shot user prompt."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        if precedents:
            # 有判例 → 拼成 few-shot user message
            parts = [_FEWSHOT_PREAMBLE]
            for i, p in enumerate(precedents, 1):
                verdict = "违规" if p.is_violation else "合规"
                vtype = p.violation_type or "N/A"
                parts.append(
                    _PRECEDENT_TEMPLATE.format(
                        index=i,
                        similarity=p.similarity,
                        content=p.content,
                        verdict=verdict,
                        violation_type=vtype,
                        reasoning=p.reasoning or "",
                    )
                )
            parts.append(_REVIEW_TEMPLATE.format(content=content))
            messages.append({"role": "user", "content": "".join(parts)})
        else:
            # 无判例 → 退化到直接审核
            messages.append({"role": "user", "content": content})

        return messages
