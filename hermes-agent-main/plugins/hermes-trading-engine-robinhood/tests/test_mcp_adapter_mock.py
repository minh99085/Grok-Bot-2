import pytest

from engine.robinhood.config import RobinhoodConfig
from engine.robinhood.robinhood_mcp_adapter import RobinhoodMCPAdapter


def test_status_without_connection(tmp_path, monkeypatch):
    monkeypatch.setenv("RH_DATA_DIR", str(tmp_path))
    cfg = RobinhoodConfig.from_env()
    adapter = RobinhoodMCPAdapter(cfg)
    st = adapter.status_dict()
    assert st["connected"] is False
    assert st["live_trading_enabled"] is False
    assert st["has_oauth_tokens"] is False


@pytest.mark.asyncio
async def test_connect_fails_without_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("RH_DATA_DIR", str(tmp_path))
    cfg = RobinhoodConfig.from_env()
    adapter = RobinhoodMCPAdapter(cfg)
    with pytest.raises(RuntimeError, match="no OAuth tokens"):
        await adapter.connect(interactive_oauth=False)