import pytest
from checker import CheckStrategyFactory, HTTPCheckStrategy


def test_strategy_factory():
    factory = CheckStrategyFactory()
    strategy = factory.get_strategy("http")
    assert isinstance(strategy, HTTPCheckStrategy)

    with pytest.raises(ValueError):
        factory.get_strategy("unknown")


@pytest.mark.asyncio
async def test_http_strategy_success(respx_mock):
    # Mocking HTTP call
    url = "https://example.com"
    respx_mock.get(url).respond(status_code=200)

    strategy = HTTPCheckStrategy()
    result = await strategy.check(url)

    assert result["is_up"] is True
    assert result["status_code"] == 200
    assert result["error"] is None


@pytest.mark.asyncio
async def test_http_strategy_failure(respx_mock):
    url = "https://error.com"
    respx_mock.get(url).respond(status_code=500)

    strategy = HTTPCheckStrategy()
    result = await strategy.check(url)

    assert result["is_up"] is False
    assert result["status_code"] == 500


@pytest.mark.asyncio
async def test_performance_strategy_success(respx_mock):
    from checker import PerformanceAuditStrategy

    url = "https://example.com"
    psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    # Mocking Google PSI Response
    mock_data = {
        "lighthouseResult": {
            "categories": {
                "performance": {"score": 0.95},
                "seo": {"score": 0.90},
                "accessibility": {"score": 1.0},
                "best-practices": {"score": 0.85},
            },
            "audits": {
                "first-contentful-paint": {"numericValue": 1200},
                "largest-contentful-paint": {"numericValue": 2500},
                "cumulative-layout-shift": {"numericValue": 0.1},
                "total-blocking-time": {"numericValue": 200},
                "final-screenshot": {"details": {"data": "data:image/png;base64,..."}},
                "screenshot-thumbnails": {
                    "details": {"items": [{"data": "...", "timing": 100}]}
                },
            },
        }
    }
    respx_mock.get(url=psi_url).respond(json=mock_data)

    strategy = PerformanceAuditStrategy()
    result = await strategy.check(url)

    assert result["perf_score"] == 95.0
    assert result["perf_seo"] == 90.0
    assert result["perf_fcp"] == 1.2
    assert result["error"] is None


@pytest.mark.asyncio
async def test_performance_strategy_rate_limit(respx_mock):
    from checker import PerformanceAuditStrategy

    url = "https://busy.com"
    psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    respx_mock.get(url=psi_url).respond(status_code=429)

    strategy = PerformanceAuditStrategy()
    # We don't want to wait for 3 retries in tests, so we might want to mock the delay too
    # but for now let's just assert it handles it (it will retry and then fail)
    import unittest.mock

    with unittest.mock.patch("asyncio.sleep", return_value=None):
        result = await strategy.check(url)

    assert "429" in result["error"] or "Limit Reached" in result["error"]
