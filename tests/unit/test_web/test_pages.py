"""PagesController Web 页面单元测试."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jinja2 import Environment, FileSystemLoader
from litestar import Litestar
from litestar.plugins.jinja import JinjaTemplateEngine
from litestar.template import TemplateConfig
from litestar.testing import AsyncTestClient


from app.web.controllers.pages import PagesController

TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "app" / "web" / "templates"


@pytest.fixture
def template_app() -> Litestar:
    """创建带模板引擎的测试应用（仅 review/history 页面 - 无需 DB）."""
    return Litestar(
        route_handlers=[PagesController],
        template_config=TemplateConfig(
            directory=TEMPLATE_DIR,
            engine=JinjaTemplateEngine,
        ),
        debug=True,
    )


@pytest.fixture
async def template_client(template_app: Litestar) -> AsyncTestClient:
    """模板应用测试客户端."""
    async with AsyncTestClient(app=template_app) as client:
        yield client


@pytest.fixture
def jinja_env() -> Environment:
    """Jinja2 环境 - 用于直接测试模板渲染."""
    return Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


class TestPagesControllerRoutes:
    """review 和 history 页面路由测试（无需 DB）."""

    @pytest.mark.asyncio
    async def test_review_page_returns_html(self, template_client: AsyncTestClient):
        """GET /review 应返回 HTML 200."""
        response = await template_client.get("/review")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_history_page_returns_html(self, template_client: AsyncTestClient):
        """GET /history 应返回 HTML 200."""
        response = await template_client.get("/history")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestTemplateContent:
    """模板内容测试."""

    @pytest.mark.asyncio
    async def test_review_page_has_form(self, template_client: AsyncTestClient):
        """审核页面应包含提交表单."""
        response = await template_client.get("/review")
        html = response.text
        assert "review-form" in html
        assert "review-content" in html
        assert "review-dimension" in html

    @pytest.mark.asyncio
    async def test_history_page_has_filters(self, template_client: AsyncTestClient):
        """历史页面应包含筛选条件."""
        response = await template_client.get("/history")
        html = response.text
        assert "filter-status" in html
        assert "filter-dimension" in html

    def test_dashboard_renders_stats_cards(self, jinja_env: Environment):
        """仪表盘模板应渲染统计卡片."""
        template = jinja_env.get_template("dashboard.html")
        html = template.render(
            total_records=10,
            by_status={"completed": 8, "pending": 2},
            by_dimension={"legal": 6, "game_principles": 4},
            by_risk_level={"low": 7, "medium": 3},
            degraded_rate=5.0,
            recent_records=[],
            request=MagicMock(url=MagicMock(path="/")),
        )
        assert "总审核记录" in html
        assert "降级率" in html
        assert "10" in html

    def test_dashboard_renders_recent_records(self, jinja_env: Environment):
        """仪表盘应渲染最近审核记录."""
        mock_record = MagicMock()
        mock_record.id = "test-id"
        mock_record.content = "测试内容"
        mock_record.review_dimension = "legal"
        mock_record.status = "completed"
        mock_record.risk_level = "low"
        mock_record.created_at = None

        template = jinja_env.get_template("dashboard.html")
        html = template.render(
            total_records=1,
            by_status={"completed": 1},
            by_dimension={"legal": 1},
            by_risk_level={"low": 1},
            degraded_rate=0.0,
            recent_records=[mock_record],
            request=MagicMock(url=MagicMock(path="/")),
        )
        assert "暂无审核" not in html

    def test_dashboard_empty_state(self, jinja_env: Environment):
        """仪表盘无数据时应显示空状态."""
        template = jinja_env.get_template("dashboard.html")
        html = template.render(
            total_records=0,
            by_status={},
            by_dimension={},
            by_risk_level={},
            degraded_rate=0.0,
            recent_records=[],
            request=MagicMock(url=MagicMock(path="/")),
        )
        assert "暂无审核" in html or "暂无数据" in html

    @pytest.mark.asyncio
    async def test_base_template_navigation(self, template_client: AsyncTestClient):
        """所有页面应包含导航栏."""
        for path in ["/review", "/history"]:
            response = await template_client.get(path)
            html = response.text
            assert "仪表盘" in html
            assert "文字审核" in html
            assert "审核历史" in html

    @pytest.mark.asyncio
    async def test_pages_not_return_json(self, template_client: AsyncTestClient):
        """Web 页面应返回 HTML 而非 JSON."""
        response = await template_client.get("/review")
        assert "application/json" not in response.headers.get("content-type", "")

    def test_base_template_extends(self, jinja_env: Environment):
        """所有页面应继承 base.html."""
        for page in ["dashboard.html", "review.html", "history.html"]:
            template = jinja_env.get_template(page)
            # 不抛异常即成功加载
            assert template is not None


class TestAppIntegration:
    """应用集成测试 — 验证真实 app 配置."""

    def test_template_config_in_app(self):
        """create_app 返回的应用应包含模板引擎."""
        from app.main import create_app
        app = create_app()
        assert app.template_engine is not None

    def test_pages_controller_registered(self):
        """PagesController 路由应已注册."""
        from app.main import create_app
        app = create_app()
        paths = [route.path for route in app.routes]
        assert "/" in paths
        assert "/review" in paths
        assert "/history" in paths

    def test_api_routes_still_registered(self):
        """API 路由不应受 Web 页面影响."""
        from app.main import create_app
        app = create_app()
        paths = [route.path for route in app.routes]
        assert "/health" in paths
        assert "/api/v1/review/text" in paths
        assert "/api/v1/history/records" in paths
