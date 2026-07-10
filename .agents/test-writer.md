# 测试编写器

基于 pytest 框架，为项目编写单元测试和集成测试。覆盖全部分层：Schema → Model → Repository → Module → Service → Controller。

## 职责

- 为指定模块编写完整的 pytest 测试套件
- 生成合理的 fixture、mock、测试数据工厂
- 区分单元测试和集成测试，落位到正确目录
- 覆盖正常路径 + 边界条件 + 异常路径 + 降级场景

## 输入

- **target**: 待测模块路径（如 `app/modules/text_review/`、`app/api/controllers/text_review.py`）
- **test_type**: `unit` | `integration` | `both`
- **coverage_target**: 期望覆盖率，默认 85%
- **existing_tests_dir**:（可选）已有测试目录，用于补充测试

## 项目测试约定

### 目录结构

```
tests/
├── conftest.py                  # 全局 fixture：test_app、test_db、test_client
├── unit/
│   ├── conftest.py              # 单元测试专用 fixture（mock 外部依赖）
│   ├── test_schemas/            # Pydantic Schema 测试
│   │   └── test_review.py
│   ├── test_models/             # ORM Model 测试（不需要真实数据库）
│   │   └── test_review_record.py
│   ├── test_services/           # Service 层单测（mock Repository + Module）
│   │   └── test_review_service.py
│   └── test_modules/            # Module 层单测（mock 外部 API）
│       ├── test_keyword_matcher.py
│       ├── test_rag_retriever.py
│       └── test_llm_judge.py
├── integration/
│   ├── conftest.py              # 集成测试 fixture（真实/内存数据库）
│   ├── test_api/                # API 端点集成测试
│   │   ├── test_health.py
│   │   ├── test_text_review.py
│   │   └── test_image_review.py
│   ├── test_database/           # 数据库集成测试
│   │   └── test_review_repo.py
│   └── test_rag/                # RAG 集成测试
│       └── test_qdrant.py
└── factories/                   # 测试数据工厂
    ├── __init__.py
    └── review_factory.py
```

### 命名规范

- 测试文件：`test_{模块名}.py`
- 测试函数：`test_{被测方法}_{场景}_{预期结果}()`
- 测试类（按需）：`class Test{被测类名}:`

### 依赖

```toml
# pyproject.toml / setup.cfg
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "pytest-mock>=3.12",
    "httpx>=0.27",                      # Litestar test client 底层
    "factory-boy>=3.3",                 # 测试数据工厂
    "asyncpg-stubs",                    # 类型提示
]
```

## 全局 Fixture 设计

### tests/conftest.py

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.main import create_app  # 工厂函数，返回 Litestar 实例


@pytest.fixture(scope="session")
def event_loop():
    """session 级别事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """测试数据库引擎（session 级别，所有测试共享一个 engine）"""
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:test@localhost:5432/safe_launch_test",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """每个测试独立的数据库 session，测试结束自动回滚"""
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin() as transaction:
            yield session
            await transaction.rollback()  # 回滚，保持数据库干净


@pytest.fixture
async def test_app(test_db) -> Litestar:
    """创建 Litestar 应用实例"""
    return create_app()


@pytest.fixture
async def test_client(test_app: Litestar) -> AsyncGenerator[AsyncTestClient, None]:
    """异步 HTTP 测试客户端"""
    async with AsyncTestClient(app=test_app) as client:
        yield client
```

### tests/unit/conftest.py

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_review_repo():
    """Mock ReviewRepository"""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.list = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_keyword_matcher():
    """Mock KeywordMatcher"""
    matcher = MagicMock()
    matcher.match = MagicMock(return_value=[])
    return matcher


@pytest.fixture
def mock_rag_retriever():
    """Mock RagRetriever"""
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[])
    return retriever


@pytest.fixture
def mock_llm_judge():
    """Mock LLMJudge (DeepSeek)"""
    judge = AsyncMock()
    judge.analyze = AsyncMock(return_value={
        "is_violation": False,
        "violation_type": None,
        "confidence": 1.0,
        "reasoning": "内容合规",
    })
    return judge


@pytest.fixture
def mock_httpx_client(mocker):
    """Mock httpx.AsyncClient"""
    return mocker.patch("httpx.AsyncClient", autospec=True)
```

### tests/factories/review_factory.py

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.review_record import ReviewRecord
from app.schemas.review import ReviewCreate


def build_review_create(**overrides) -> ReviewCreate:
    """构建 ReviewCreate Schema 测试数据"""
    defaults = {
        "content": "这是一段测试文本内容",
        "content_type": "text",
        "review_dimension": "legal",
    }
    defaults.update(overrides)
    return ReviewCreate(**defaults)


def build_review_record(**overrides) -> ReviewRecord:
    """构建 ReviewRecord ORM 对象（不写入数据库）"""
    defaults = {
        "id": uuid.uuid4(),
        "content": "这是一段测试文本内容",
        "content_type": "text",
        "review_dimension": "legal",
        "status": "completed",
        "review_result": {"is_violation": False, "layers": []},
        "risk_level": "low",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return ReviewRecord(**defaults)
```

## 测试模板

### 1. Pydantic Schema 单元测试

```python
"""app/schemas/review.py 的单元测试"""
import pytest
from pydantic import ValidationError

from app.schemas.review import ReviewCreate


class TestReviewCreate:
    """ReviewCreate Schema 测试"""

    def test_valid_minimal_fields(self):
        """有效的最小字段组合应通过校验"""
        data = ReviewCreate(content="测试", content_type="text", review_dimension="legal")
        assert data.content == "测试"
        assert data.content_type == "text"

    def test_content_exceeds_max_length_raises_error(self):
        """content 超过最大长度应抛出 ValidationError"""
        with pytest.raises(ValidationError) as exc:
            ReviewCreate(content="x" * 10001, content_type="text", review_dimension="legal")
        assert "content" in str(exc.value)

    def test_empty_content_raises_error(self):
        """空 content 应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ReviewCreate(content="", content_type="text", review_dimension="legal")

    def test_invalid_review_dimension_raises_error(self):
        """非法的 review_dimension 值应抛出 ValidationError"""
        with pytest.raises(ValidationError):
            ReviewCreate(content="测试", content_type="text", review_dimension="invalid_dim")

    @pytest.mark.parametrize("dimension", [
        "legal", "game_principles", "compliance", "art_assets"
    ])
    def test_all_valid_dimensions_pass(self, dimension):
        """所有合法 review_dimension 值应通过校验"""
        data = ReviewCreate(content="测试", content_type="text", review_dimension=dimension)
        assert data.review_dimension == dimension

    @pytest.mark.parametrize("content,expected", [
        ("正常内容", False),
        ("<script>alert(1)</script>", True),  # XSS 尝试
        ("", True),  # 空字符串
        (None, True),  # None
        ("   ", True),  # 仅空白
    ])
    def test_content_validation_edge_cases(self, content, expected):
        """content 边界条件测试"""
        if expected:
            with pytest.raises(ValidationError):
                ReviewCreate(content=content, content_type="text", review_dimension="legal")
        else:
            ReviewCreate(content=content, content_type="text", review_dimension="legal")
```

### 2. Service 层单元测试（mock 外部依赖）

```python
"""app/services/review_service.py 的单元测试"""
import uuid

import pytest
from unittest.mock import AsyncMock

from app.schemas.review import ReviewCreate, ReviewResponse
from app.services.review_service import ReviewService


class TestReviewService:
    """ReviewService 单元测试 — 所有依赖均为 Mock"""

    @pytest.fixture
    def service(self, mock_review_repo, mock_keyword_matcher, mock_rag_retriever, mock_llm_judge):
        return ReviewService(
            review_repo=mock_review_repo,
            keyword_matcher=mock_keyword_matcher,
            rag_retriever=mock_rag_retriever,
            llm_judge=mock_llm_judge,
        )

    @pytest.mark.asyncio
    async def test_create_review_passes_content(self, service, mock_review_repo, mock_llm_judge):
        """正常审核内容 — 应返回通过结果"""
        # Arrange
        data = ReviewCreate(content="正常游戏描述", content_type="text", review_dimension="legal")
        mock_review_repo.create.return_value = ...  # 构造返回值
        mock_llm_judge.analyze.return_value = {
            "is_violation": False, "confidence": 0.98, "reasoning": "合规"
        }

        # Act
        result = await service.create_review(data)

        # Assert
        assert result.is_violation is False
        mock_review_repo.create.assert_awaited_once()
        mock_llm_judge.analyze.assert_awaited_once_with(data.content)

    @pytest.mark.asyncio
    async def test_create_review_detects_violation(self, service, mock_llm_judge):
        """检测到违规内容 — 应返回违规结果"""
        mock_llm_judge.analyze.return_value = {
            "is_violation": True,
            "violation_type": "涉政",
            "confidence": 0.95,
            "reasoning": "包含敏感政治表述",
        }
        data = ReviewCreate(content="敏感内容", content_type="text", review_dimension="legal")

        result = await service.create_review(data)

        assert result.is_violation is True
        assert result.violation_type == "涉政"

    @pytest.mark.asyncio
    async def test_degraded_mode_when_llm_unavailable(self, service, mock_llm_judge, mock_keyword_matcher):
        """LLM 不可用时应降级 — 仅用关键词 + RAG 结果，标注 degraded"""
        mock_llm_judge.analyze.side_effect = Exception("DeepSeek API 超时")
        mock_keyword_matcher.match.return_value = []  # L1 未命中
        data = ReviewCreate(content="测试", content_type="text", review_dimension="legal")

        result = await service.create_review(data)

        assert result.degraded is True
        assert "llm" in result.skipped_layers

    @pytest.mark.asyncio
    async def test_create_review_logs_and_raises_when_all_layers_fail(self, service, mock_keyword_matcher, mock_llm_judge):
        """所有检测层均不可用时应抛出异常"""
        mock_keyword_matcher.match.side_effect = Exception("关键词库损坏")
        mock_llm_judge.analyze.side_effect = Exception("LLM 不可用")
        data = ReviewCreate(content="测试", content_type="text", review_dimension="legal")

        with pytest.raises(Exception, match="所有审核层不可用"):
            await service.create_review(data)
```

### 3. API 集成测试

```python
"""POST /api/v1/review/text 集成测试"""
import pytest
from httpx import AsyncClient


class TestTextReviewAPI:
    """文字审核 API 集成测试"""

    @pytest.mark.asyncio
    async def test_review_text_success(self, test_client: AsyncClient):
        """正常请求应返回 201 + ReviewResponse"""
        response = await test_client.post(
            "/api/v1/review/text",
            json={
                "content": "这是一段游戏剧情描述",
                "content_type": "text",
                "review_dimension": "legal",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["is_violation"] in (True, False)
        assert "layers" in data
        assert data["review_dimension"] == "legal"

    @pytest.mark.asyncio
    async def test_review_text_empty_content_returns_422(self, test_client: AsyncClient):
        """空内容应返回 422 Unprocessable Entity"""
        response = await test_client.post(
            "/api/v1/review/text",
            json={"content": "", "content_type": "text", "review_dimension": "legal"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_review_text_missing_required_field_returns_422(self, test_client: AsyncClient):
        """缺少必填字段应返回 422"""
        response = await test_client.post(
            "/api/v1/review/text",
            json={"content": "测试"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_review_text_batch(self, test_client: AsyncClient):
        """批量审核应返回对应数量的结果"""
        items = [
            {"content": f"测试内容 {i}", "content_type": "text", "review_dimension": "legal"}
            for i in range(3)
        ]
        response = await test_client.post("/api/v1/review/text/batch", json=items)
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_review_text_batch_exceeds_limit_returns_422(self, test_client: AsyncClient):
        """批量超过上限应返回 422"""
        items = [
            {"content": f"测试 {i}", "content_type": "text", "review_dimension": "legal"}
            for i in range(101)  # 假设上限 100
        ]
        response = await test_client.post("/api/v1/review/text/batch", json=items)
        assert response.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", [
        "/api/v1/review/text",
        "/api/v1/review/image",
    ])
    async def test_review_endpoints_reject_non_json(self, test_client: AsyncClient, endpoint):
        """非 JSON Content-Type 应返回 415"""
        response = await test_client.post(endpoint, content=b"raw data")
        assert response.status_code in (415, 422)
```

### 4. 数据库集成测试

```python
"""Repository 层集成测试 — 使用真实测试数据库"""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.repos.review_repo import ReviewRepository
from app.schemas.review import ReviewCreate
from tests.factories.review_factory import build_review_create


class TestReviewRepository:
    """ReviewRepository 集成测试"""

    @pytest.fixture
    def repo(self, test_db: AsyncSession):
        return ReviewRepository(test_db)

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, repo: ReviewRepository):
        """创建后应能正确查询到"""
        data = build_review_create(content="测试内容")

        created = await repo.create(data)
        retrieved = await repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.content == "测试内容"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_returns_none(self, repo: ReviewRepository):
        """查询不存在的记录应返回 None"""
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, repo: ReviewRepository):
        """分页查询应返回正确的数量和页码"""
        # 先创建 5 条记录
        for i in range(5):
            data = build_review_create(content=f"测试 {i}")
            await repo.create(data)

        result = await repo.list(page=1, page_size=3)

        assert len(result.items) == 3
        assert result.total == 5
        assert result.page == 1
        assert result.page_size == 3

    @pytest.mark.asyncio
    async def test_update_modifies_fields(self, repo: ReviewRepository):
        """更新操作应正确修改字段"""
        data = build_review_create(content="原始内容")
        created = await repo.create(data)

        updated = await repo.update(created.id, {"status": "reviewing"})

        assert updated.status == "reviewing"
        assert updated.content == "原始内容"  # 未修改的字段不变

    @pytest.mark.asyncio
    async def test_delete_removes_record(self, repo: ReviewRepository):
        """删除后查询应返回 None"""
        data = build_review_create()
        created = await repo.create(data)

        await repo.delete(created.id)

        assert await repo.get_by_id(created.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises_not_found(self, repo: ReviewRepository):
        """删除不存在的记录应抛出异常"""
        with pytest.raises(Exception):
            await repo.delete(uuid.uuid4())
```

### 5. Module 层单元测试（LLM Mock）

```python
"""DeepSeek LLM 判定器单元测试"""
import json

import pytest
from unittest.mock import AsyncMock, patch

from app.modules.text_review.llm_judge import DeepSeekAnalyzer


class TestDeepSeekAnalyzer:
    """DeepSeek 判定器测试 — Mock HTTP 层"""

    @pytest.fixture
    def analyzer(self):
        return DeepSeekAnalyzer(
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )

    @pytest.mark.asyncio
    async def test_analyze_returns_structured_json(self, analyzer):
        """LLM 返回合法 JSON 时应正确解析"""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "is_violation": False,
                        "violation_type": None,
                        "confidence": 0.98,
                        "reasoning": "内容合规，无敏感信息",
                    })
                }
            }]
        }
        mock_client = AsyncMock()
        mock_client.post.return_value.json.return_value = mock_response
        mock_client.post.return_value.status_code = 200

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyzer.analyze("正常游戏内容")

        assert result["is_violation"] is False
        assert result["confidence"] == 0.98

    @pytest.mark.asyncio
    async def test_analyze_malformed_json_returns_error_result(self, analyzer):
        """LLM 返回非法 JSON 时应返回错误标记"""
        mock_response = {
            "choices": [{
                "message": {"content": "这不是 JSON"}
            }]
        }
        mock_client = AsyncMock()
        mock_client.post.return_value.json.return_value = mock_response
        mock_client.post.return_value.status_code = 200

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyzer.analyze("测试")

        assert result["is_violation"] is None
        assert "error" in result

    @pytest.mark.asyncio
    async def test_analyze_api_timeout_returns_degraded(self, analyzer):
        """API 超时应返回降级结果"""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection timed out")

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await analyzer.analyze("测试", timeout=5)

        assert result["is_violation"] is None
        assert result["error"] == "timeout"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("content", [
        "",
        "   ",
        None,
        "x" * 100000,  # 超长内容
    ])
    async def test_analyze_invalid_input_raises(self, analyzer, content):
        """非法输入应在调用 LLM 之前拦截"""
        with pytest.raises(ValueError):
            await analyzer.analyze(content)
```

## 输出格式

```
## 测试生成报告

**目标**: {target}
**类型**: {test_type}

### 生成文件

| 文件 | 测试数 | 覆盖层 |
|------|--------|--------|
| tests/unit/test_schemas/test_review.py | 8 | Schema |
| tests/unit/test_modules/test_llm_judge.py | 6 | Module |
| tests/unit/test_services/test_review_service.py | 5 | Service |
| tests/integration/test_api/test_text_review.py | 7 | API |
| tests/integration/test_database/test_review_repo.py | 6 | Repository |
| tests/conftest.py | - | 全局 fixture |
| tests/factories/review_factory.py | - | 数据工厂 |

### 覆盖场景

| 类别 | 场景 |
|------|------|
| 正常路径 | 合规内容通过、违规内容检出、批量审核 |
| 边界条件 | 空内容、超长内容、特殊字符、Unicode |
| 异常路径 | API 超时、LLM 返回非法 JSON、数据库连接失败 |
| 降级场景 | L1 命中跳过 L2/L3、LLM 不可用降级、Qdrant 不可用跳过 |
| 并发场景 | 批量审核并发控制、Semaphore 限流 |

### 运行测试

```bash
# 运行全部测试
pytest tests/ -v

# 仅运行单元测试
pytest tests/unit/ -v

# 运行并生成覆盖率报告
pytest tests/ --cov=app --cov-report=html

# 仅运行指定模块
pytest tests/unit/test_modules/test_llm_judge.py -v
```
```

## 关键规则

- **测试数据库用独立 DB**（`safe_launch_test`），不与开发 DB 混淆
- **每个测试用例独立**：不依赖其他用例的副作用，通过 fixture 的 rollback 保证隔离
- **Mock 只 Mock 本层之外**：Service 单测 Mock Repository + Module，不 Mock 本层逻辑
- **集成测试覆盖真实 IO**：数据库用真实 PostgreSQL、API 用 `AsyncTestClient`
- **参数化覆盖枚举**：所有 enum 字段用 `@pytest.mark.parametrize` 覆盖全部合法值和非法值
- **异步测试标记**：所有 `async def` 测试必须用 `@pytest.mark.asyncio`
- **AAA 模式**：每个测试函数保持 Arrange / Act / Assert 三段式结构
- **工厂优于字面量**：用 factory 函数构造测试数据，不要在每个测试中手写 dict
- **降级场景必测**：本项目核心特色，每层降级逻辑必须有对应测试
- **外部服务不真实调用**：DeepSeek、Qdrant、OpenAI、图片检测服务全部 Mock，用集成环境单独验证
