"""Shared tool name constants for Robinhood Trading MCP."""

PLACE_TOOLS = frozenset({"place_equity_order", "place_option_order"})
REVIEW_TOOLS = frozenset({"review_equity_order", "review_option_order"})
ORDER_TOOLS = PLACE_TOOLS | REVIEW_TOOLS