"""Tier-2 #5 maker / passive-fill SHADOW simulator (PAPER / RESEARCH ONLY).

Simulates resting a PASSIVE buy at the bid (vs crossing the spread as a taker) using REAL
cross-tick order-book evolution, with a queue-position model and adverse-selection markout —
to measure, in SHADOW, the maker fill rate, the spread actually captured, and the adverse
selection, BEFORE wiring passive fills into the live paper OMS. It tracks resting orders in
its own bounded ledger and NEVER opens a real paper position or trades; pure given the
observations the trainer feeds it each tick.

Model (conservative):
* place() rests a buy at ``rest_price`` (the touch bid) with ``queue_ahead_usd`` = the
  resting bid-side depth in front of us at that level.
* each tick the level is "active" (the market's best ask <= our rest price -> sellers are
  crossing to the bid), we consume our queue by an estimated traded volume; when the queue
  clears we FILL at ``rest_price`` (we captured ~the half/full spread vs the taker).
* after fill we track the mid for ``markout_ticks`` ticks -> adverse-selection markout
  (mid drifts DOWN after we bought = we were picked off).
* unfilled orders EXPIRE after ``max_resting_ticks`` (a realistic non-fill).
"""

from __future__ import annotations

from dataclasses import dataclass, field

RESTING, FILLED, EXPIRED, DONE = "resting", "filled", "expired", "done"


def _f(x, d: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


@dataclass
class RestingOrder:
    market_id: str
    rest_price: float
    size_usd: float
    queue_ahead_usd: float
    placed_tick: int
    mid_at_place: float
    state: str = RESTING
    fill_tick: int = -1
    fill_mid: float = 0.0
    markout_mid: float = 0.0          # latest mid observed after fill
    ticks_since_fill: int = 0


class MakerFillSimulator:
    """Bounded shadow ledger of passive resting orders + fill/markout metrics. Never trades."""

    def __init__(self, *, max_orders: int = 50, max_resting_ticks: int = 20,
                 markout_ticks: int = 5, turnover_per_tick: float = 0.10):
        self.max_orders = int(max_orders)
        self.max_resting_ticks = int(max_resting_ticks)
        self.markout_ticks = int(markout_ticks)
        self.turnover_per_tick = float(turnover_per_tick)
        self.orders: list[RestingOrder] = []
        # cumulative metrics
        self.placed = 0
        self.filled = 0
        self.expired = 0
        self._spread_captured: list = []     # mid_at_place - rest_price (per fill)
        self._fill_latency: list = []        # ticks to fill
        self._adverse_markout: list = []     # (markout_mid - rest_price) per filled order

    def has(self, market_id: str) -> bool:
        return any(o.market_id == market_id and o.state == RESTING for o in self.orders)

    def place(self, *, market_id: str, rest_price: float, mid: float,
              depth_usd: float, size_usd: float, tick: int) -> bool:
        """Rest a passive buy at ``rest_price`` (the bid). ``depth_usd`` is the resting
        bid-side depth in front of us (our queue). Bounded + de-duplicated."""
        rest_price = _f(rest_price)
        if rest_price <= 0.0 or self.has(market_id):
            return False
        if len([o for o in self.orders if o.state == RESTING]) >= self.max_orders:
            return False
        self.orders.append(RestingOrder(
            market_id=market_id, rest_price=rest_price, size_usd=_f(size_usd),
            queue_ahead_usd=max(0.0, _f(depth_usd)), placed_tick=int(tick),
            mid_at_place=_f(mid)))
        self.placed += 1
        return True

    def update(self, observations: dict, *, tick: int) -> None:
        """Advance the ledger one tick. ``observations``: ``{market_id: {best_ask, best_bid,
        mid, depth_usd}}`` (current real book). Fills/expires/markout-tracks resting orders."""
        obs = observations or {}
        for o in self.orders:
            if o.state == FILLED:
                ob = obs.get(o.market_id)
                if ob is not None:
                    o.markout_mid = _f(ob.get("mid"), o.markout_mid)
                o.ticks_since_fill += 1
                if o.ticks_since_fill >= self.markout_ticks:
                    self._adverse_markout.append(round(o.markout_mid - o.rest_price, 6))
                    o.state = DONE
                continue
            if o.state != RESTING:
                continue
            if tick - o.placed_tick >= self.max_resting_ticks:
                o.state = EXPIRED
                self.expired += 1
                continue
            ob = obs.get(o.market_id)
            if ob is None:
                continue
            best_ask = _f(ob.get("best_ask"))
            # level is "active" when the market's best ask reaches our resting bid (sellers
            # crossing to the bid) -> consume our queue by an estimated traded volume.
            if best_ask > 0.0 and best_ask <= o.rest_price + 1e-9:
                traded = max(0.0, _f(ob.get("depth_usd"), o.size_usd)) * self.turnover_per_tick
                o.queue_ahead_usd -= max(traded, o.size_usd)   # at least our own size clears
                if o.queue_ahead_usd <= 0.0:
                    o.state = FILLED
                    o.fill_tick = int(tick)
                    o.fill_mid = _f(ob.get("mid"), o.mid_at_place)
                    o.markout_mid = o.fill_mid
                    self.filled += 1
                    self._spread_captured.append(round(o.mid_at_place - o.rest_price, 6))
                    self._fill_latency.append(int(tick) - o.placed_tick)
        # bound memory: drop terminal orders beyond a window
        terminal = [o for o in self.orders if o.state in (EXPIRED, DONE)]
        if len(terminal) > self.max_orders * 4:
            keep_terminal = terminal[-self.max_orders * 2:]
            self.orders = [o for o in self.orders if o.state in (RESTING, FILLED)] + keep_terminal

    @staticmethod
    def _avg(xs: list):
        return round(sum(xs) / len(xs), 6) if xs else 0.0

    def metrics(self) -> dict:
        resting = sum(1 for o in self.orders if o.state == RESTING)
        attempted = self.filled + self.expired
        return {
            "schema": "maker_fill_sim/1.0", "paper_only": True, "shadow_only": True,
            "live_trading_enabled": False,
            "orders_placed": self.placed,
            "orders_resting": resting,
            "orders_filled": self.filled,
            "orders_expired": self.expired,
            "fill_rate": round(self.filled / attempted, 4) if attempted else 0.0,
            "avg_spread_captured": self._avg(self._spread_captured),
            "avg_fill_latency_ticks": self._avg(self._fill_latency),
            "avg_adverse_markout": self._avg(self._adverse_markout),
            "maker_edge_after_adverse": round(
                self._avg(self._spread_captured) + self._avg(self._adverse_markout), 6),
            "markout_samples": len(self._adverse_markout),
        }
