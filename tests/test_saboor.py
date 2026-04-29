"""
Focused unit tests for the Saboor investing system.
All tests are local-only: no network calls, no Supabase, no Alpaca.

Heavy third-party dependencies (supabase, anthropic, dotenv) are mocked at the
sys.modules level so the source modules can be imported without a full venv.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import date

# ── Mock heavy external dependencies before importing any source modules ───────
_MOCK_MODULES = [
    "supabase", "supabase.client",
    "anthropic",
    "dotenv",
]
for _m in _MOCK_MODULES:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Mock supabase_client so db.queries can be imported cleanly
_supabase_client_mock = MagicMock()
sys.modules.setdefault("db.supabase_client", _supabase_client_mock)

# Force source module imports (needed for @patch decorator resolution)
import tools.technical        # no heavy deps — pure Python
import agents.analyst         # imports tools.claude_client (anthropic mocked)
import agents.risk_guardian   # imports db.queries → db.supabase_client (mocked)
import db.queries
import phases.eod


# ── 1. 14% position cap enforcement ──────────────────────────────────────────

class TestRiskGuardianCap(unittest.TestCase):

    def _portfolio(self, total_value=10_000):
        return {"total_value": total_value, "cash": total_value * 0.5,
                "equity": total_value * 0.5, "daily_pl": 0.0}

    @patch("agents.risk_guardian._live_entry_check", return_value=(True, "ok"))
    @patch("agents.risk_guardian.get_position_by_ticker", return_value=None)
    @patch("agents.risk_guardian.get_portfolio_value")
    def test_buy_blocked_over_14pct(self, mock_pv, mock_pos, mock_entry):
        from agents.risk_guardian import validate_order
        mock_pv.return_value = self._portfolio()
        # 15 * $100 = $1,500 = 15% of $10,000 → should be blocked
        approved, reason = validate_order("AAPL", "buy", 15, 100.0, "core")
        self.assertFalse(approved)
        self.assertIn("14%", reason)

    @patch("agents.risk_guardian._live_entry_check", return_value=(True, "ok"))
    @patch("agents.risk_guardian.get_position_by_ticker", return_value=None)
    @patch("agents.risk_guardian.get_portfolio_value")
    def test_buy_approved_under_14pct(self, mock_pv, mock_pos, mock_entry):
        from agents.risk_guardian import validate_order
        mock_pv.return_value = self._portfolio()
        # 13 * $100 = $1,300 = 13% → approved
        approved, _ = validate_order("AAPL", "buy", 13, 100.0, "core")
        self.assertTrue(approved)

    @patch("agents.risk_guardian.get_portfolio_value")
    @patch("agents.risk_guardian.get_position_by_ticker", return_value=None)
    def test_exit_always_approved(self, mock_pos, mock_pv):
        from agents.risk_guardian import validate_order
        mock_pv.return_value = self._portfolio()
        approved, _ = validate_order("AAPL", "exit", 100, 100.0)
        self.assertTrue(approved)

    @patch("agents.risk_guardian.get_portfolio_value")
    @patch("agents.risk_guardian.get_position_by_ticker", return_value=None)
    def test_trim_always_approved(self, mock_pos, mock_pv):
        from agents.risk_guardian import validate_order
        mock_pv.return_value = self._portfolio()
        approved, _ = validate_order("AAPL", "trim", 5, 100.0)
        self.assertTrue(approved)

    @patch("agents.risk_guardian._live_entry_check", return_value=(True, "ok"))
    @patch("agents.risk_guardian.get_position_by_ticker")
    @patch("agents.risk_guardian.get_portfolio_value")
    def test_add_accounts_for_existing_shares(self, mock_pv, mock_pos, mock_entry):
        from agents.risk_guardian import validate_order
        mock_pv.return_value = self._portfolio()
        mock_pos.return_value = {"shares": 10, "entry_price": 100.0}
        # (10+4)*100 = $1,400 = exactly 14% → approved
        approved, _ = validate_order("AAPL", "add", 4, 100.0, "core")
        self.assertTrue(approved)
        # (10+5)*100 = $1,500 = 15% → blocked
        approved, reason = validate_order("AAPL", "add", 5, 100.0, "core")
        self.assertFalse(approved)
        self.assertIn("14%", reason)

    @patch("agents.risk_guardian.get_position_by_ticker", return_value=None)
    @patch("agents.risk_guardian.get_portfolio_value")
    def test_max_shares_respects_target_weight(self, mock_pv, mock_pos):
        from agents.risk_guardian import max_shares_for_position
        mock_pv.return_value = self._portfolio()
        # 8% of $10,000 = $800, at $100/share = 8 shares
        result = max_shares_for_position(price=100.0, position_weight_pct=8.0, ticker="AAPL")
        self.assertEqual(result, 8)

    @patch("agents.risk_guardian.get_position_by_ticker", return_value=None)
    @patch("agents.risk_guardian.get_portfolio_value")
    def test_max_shares_never_exceeds_14pct(self, mock_pv, mock_pos):
        from agents.risk_guardian import max_shares_for_position
        mock_pv.return_value = self._portfolio()
        # 20% requested but hard cap at 14% = $1,400 → 14 shares at $100
        result = max_shares_for_position(price=100.0, position_weight_pct=20.0, ticker="AAPL")
        self.assertEqual(result, 14)


# ── 2. RSI > 78 blocks new buys/adds ─────────────────────────────────────────

class TestRsiEntryFilter(unittest.TestCase):

    def _bars(self, prices):
        return [{"close": p, "volume": 1_000_000} for p in prices]

    @patch("agents.risk_guardian.get_bars")
    def test_rsi_over_78_blocks(self, mock_bars):
        # Steep linear uptrend → RSI near 100
        mock_bars.return_value = self._bars([100.0 + i for i in range(210)])
        from agents.risk_guardian import _live_entry_check
        ok, reason = _live_entry_check("AAPL")
        self.assertFalse(ok)
        self.assertIn("RSI", reason)
        self.assertIn("blocked", reason)

    @patch("agents.risk_guardian.get_bars")
    def test_rsi_neutral_oscillation_passes(self, mock_bars):
        # Alternating ±1 → equal gains/losses → RSI = 50
        prices = []
        p = 150.0
        for i in range(210):
            prices.append(p)
            p += 1.0 if i % 2 == 0 else -1.0
        mock_bars.return_value = self._bars(prices)
        from agents.risk_guardian import _live_entry_check
        ok, reason = _live_entry_check("AAPL")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")


# ── 3. Price > 150% above MA200 blocks new buys/adds ─────────────────────────

class TestMa200EntryFilter(unittest.TestCase):
    """
    Build fixtures where RSI stays neutral (alternating ±1) while the
    MA200 extension crosses above or stays below 150%.

    Setup: 190 bars at a low base price, then 20 bars alternating
    high/low. The 200-bar average stays near the base, so the current
    price sitting well above it creates the desired extension.

    MA200 ≈ (180 * base + 20 * top) / 200
    Extension = (top / MA200 - 1) * 100
    RSI uses last 14 deltas which alternate ±1 → gains = losses → RSI = 50
    """

    def _bars(self, prices):
        return [{"close": p, "volume": 1_000_000} for p in prices]

    def _make_prices(self, base, top, total=210):
        """190 bars at base, then 20 bars oscillating top / (top-1)."""
        prices = [float(base)] * (total - 20)
        for i in range(20):
            prices.append(float(top) if i % 2 == 0 else float(top) - 1.0)
        return prices

    @patch("agents.risk_guardian.get_bars")
    def test_price_over_150pct_above_ma200_blocks(self, mock_bars):
        # base=$10, top=$50 → MA200 ≈ 13.95 → extension ≈ 251% > 150%
        mock_bars.return_value = self._bars(self._make_prices(base=10, top=50))
        from agents.risk_guardian import _live_entry_check
        ok, reason = _live_entry_check("TSLA")
        self.assertFalse(ok)
        self.assertIn("MA200", reason)
        self.assertIn("blocked", reason)

    @patch("agents.risk_guardian.get_bars")
    def test_price_under_150pct_above_ma200_passes(self, mock_bars):
        # base=$10, top=$21 → MA200 ≈ 11.1 → extension ≈ 89% < 150%
        mock_bars.return_value = self._bars(self._make_prices(base=10, top=21))
        from agents.risk_guardian import _live_entry_check
        ok, _ = _live_entry_check("TSLA")
        self.assertTrue(ok)


# ── 4. Pure-speculation hard filter ──────────────────────────────────────────

class TestPureSpeculationFilter(unittest.TestCase):

    def test_all_three_criteria_triggers_exclusion(self):
        from agents.analyst import _is_pure_speculation
        self.assertTrue(_is_pure_speculation(
            {"fcf_positive": False, "pe_ratio": 200, "roe": -0.05}
        ))

    def test_fcf_positive_prevents_exclusion(self):
        from agents.analyst import _is_pure_speculation
        self.assertFalse(_is_pure_speculation(
            {"fcf_positive": True, "pe_ratio": 200, "roe": -0.05}
        ))

    def test_pe_below_150_prevents_exclusion(self):
        from agents.analyst import _is_pure_speculation
        self.assertFalse(_is_pure_speculation(
            {"fcf_positive": False, "pe_ratio": 100, "roe": -0.05}
        ))

    def test_roe_positive_prevents_exclusion(self):
        from agents.analyst import _is_pure_speculation
        self.assertFalse(_is_pure_speculation(
            {"fcf_positive": False, "pe_ratio": 200, "roe": 0.05}
        ))

    def test_none_pe_prevents_exclusion(self):
        from agents.analyst import _is_pure_speculation
        self.assertFalse(_is_pure_speculation(
            {"fcf_positive": False, "pe_ratio": None, "roe": -0.05}
        ))

    def test_non_compliant_filtered_by_normalize(self):
        from agents.analyst import _normalize_score
        self.assertIsNone(_normalize_score(
            {"sharia_status": "non_compliant", "quality_score": 80,
             "combined_score": 75, "position_weight_pct": 8}
        ))

    def test_borderline_sharia_filtered_by_normalize(self):
        from agents.analyst import _normalize_score
        self.assertIsNone(_normalize_score(
            {"sharia_status": "borderline", "quality_score": 80,
             "combined_score": 75, "position_weight_pct": 8}
        ))

    def test_position_weight_capped_at_14_in_normalize(self):
        from agents.analyst import _normalize_score
        result = _normalize_score({
            "sharia_status": "compliant", "quality_score": 80,
            "entry_timing_score": 60, "combined_score": 76,
            "position_weight_pct": 20,
        })
        self.assertIsNotNone(result)
        self.assertEqual(result["position_weight_pct"], 14.0)


# ── 5. save_position updates existing row — no duplicate insert ───────────────

class TestSavePositionUpsert(unittest.TestCase):

    def _mock_client(self):
        mc = MagicMock()
        mc.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mc.table.return_value.insert.return_value.execute.return_value = MagicMock()
        return mc

    @patch("db.queries.get_client")
    @patch("db.queries.get_position_by_ticker")
    def test_add_calls_update_not_insert(self, mock_get_pos, mock_get_client):
        mock_get_pos.return_value = {
            "id": 42, "ticker": "AAPL", "shares": 10.0, "entry_price": 150.0,
            "thesis": "original", "quality_score": 80.0,
            "momentum_score": 60.0, "combined_score": 76.0, "pnl": 0.0
        }
        mc = self._mock_client()
        mock_get_client.return_value = mc

        from db.queries import save_position
        save_position("AAPL", "core", 5, 160.0, "updated thesis",
                      date(2026, 4, 28), quality_score=82.0)

        mc.table.return_value.insert.assert_not_called()
        mc.table.return_value.update.assert_called_once()

    @patch("db.queries.get_client")
    @patch("db.queries.get_position_by_ticker")
    def test_new_position_calls_insert(self, mock_get_pos, mock_get_client):
        mock_get_pos.return_value = None
        mc = self._mock_client()
        mock_get_client.return_value = mc

        from db.queries import save_position
        save_position("NVDA", "core", 5, 200.0, "AI chip leader",
                      date(2026, 4, 28), quality_score=90.0)

        mc.table.return_value.insert.assert_called_once()
        mc.table.return_value.update.assert_not_called()

    @patch("db.queries.get_client")
    @patch("db.queries.get_position_by_ticker")
    def test_add_computes_weighted_avg_entry_price(self, mock_get_pos, mock_get_client):
        mock_get_pos.return_value = {
            "id": 1, "ticker": "MSFT", "shares": 10.0, "entry_price": 100.0,
            "thesis": "t", "quality_score": None, "momentum_score": None,
            "combined_score": None, "pnl": 0.0
        }
        mc = self._mock_client()
        mock_get_client.return_value = mc

        from db.queries import save_position
        save_position("MSFT", "core", 10, 120.0, "t", date(2026, 4, 28))

        # (10*100 + 10*120) / 20 = $110
        update_payload = mc.table.return_value.update.call_args[0][0]
        self.assertAlmostEqual(update_payload["entry_price"], 110.0)
        self.assertAlmostEqual(update_payload["shares"], 20.0)


# ── 6. reduce_position decreases shares and accumulates realized P&L ──────────

class TestReducePosition(unittest.TestCase):

    @patch("db.queries.get_client")
    @patch("db.queries.get_position_by_ticker")
    def test_trim_reduces_shares_and_adds_pnl(self, mock_get_pos, mock_client):
        mock_get_pos.return_value = {
            "id": 7, "ticker": "AAPL", "shares": 20.0,
            "entry_price": 100.0, "pnl": 50.0
        }
        mc = MagicMock()
        mock_client.return_value = mc

        from db.queries import reduce_position
        # Sell 5 shares at $120: realized P&L = (120-100)*5 = +$100
        reduce_position("AAPL", 5, 120.0, "valuation trim")

        update_payload = mc.table.return_value.update.call_args[0][0]
        self.assertAlmostEqual(update_payload["shares"], 15.0)
        self.assertAlmostEqual(update_payload["pnl"], 150.0)  # 50 existing + 100 new

    @patch("db.queries.close_position")
    @patch("db.queries.get_position_by_ticker")
    def test_trim_all_shares_delegates_to_close_position(self, mock_get_pos, mock_close):
        mock_get_pos.return_value = {
            "id": 7, "ticker": "AAPL", "shares": 5.0, "entry_price": 100.0, "pnl": 0.0
        }
        from db.queries import reduce_position
        reduce_position("AAPL", 10, 110.0, "full exit via trim")
        mock_close.assert_called_once_with("AAPL", 110.0, "full exit via trim")

    @patch("db.queries.get_position_by_ticker", return_value=None)
    def test_trim_missing_position_is_noop(self, _):
        from db.queries import reduce_position
        reduce_position("FAKE", 5, 100.0, "reason")  # must not raise


# ── 7. EOD phase does not close any positions ─────────────────────────────────

class TestEodNoAutoClose(unittest.TestCase):

    def test_eod_does_not_import_close_or_reduce(self):
        import ast, inspect
        source = inspect.getsource(phases.eod)
        tree = ast.parse(source)
        imported_from_queries = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "db.queries":
                for alias in node.names:
                    imported_from_queries.add(alias.asname or alias.name)
        self.assertNotIn("close_position", imported_from_queries)
        self.assertNotIn("reduce_position", imported_from_queries)

    def test_eod_source_has_no_position_close_calls(self):
        import inspect
        source = inspect.getsource(phases.eod)
        self.assertNotIn("close_position(", source)
        self.assertNotIn("reduce_position(", source)


# ── 8. Benchmark queries use previous-day date, not today ────────────────────

class TestBenchmarkPreviousDate(unittest.TestCase):

    @patch("db.queries.get_client")
    def test_save_benchmark_queries_lt_trading_date(self, mock_client):
        mc = MagicMock()
        # No previous row → cumulative starts at daily return
        mc.table.return_value.select.return_value.lt.return_value \
            .order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_client.return_value = mc

        from db.queries import save_benchmark
        trading_date = date(2026, 4, 28)
        save_benchmark(trading_date, 10_500.0, 0.5, 0.2)

        lt_call = mc.table.return_value.select.return_value.lt.call_args
        self.assertEqual(lt_call[0][0], "date")
        self.assertEqual(lt_call[0][1], trading_date.isoformat())

    @patch("db.queries.get_client")
    def test_get_previous_portfolio_value_queries_lt_before_date(self, mock_client):
        mc = MagicMock()
        mc.table.return_value.select.return_value.lt.return_value \
            .order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"portfolio_value": 9_800.0}]
        )
        mock_client.return_value = mc

        from db.queries import get_previous_portfolio_value
        result = get_previous_portfolio_value(before_date=date(2026, 4, 28))
        self.assertEqual(result, 9_800.0)
        lt_call = mc.table.return_value.select.return_value.lt.call_args
        self.assertEqual(lt_call[0][1], "2026-04-28")


# ── 9. Premarket save_watchlist preserves acted_on flag ──────────────────────

class TestSaveWatchlistPreservesActedOn(unittest.TestCase):

    def _item(self, ticker):
        return {
            "ticker": ticker, "quality_score": 80, "momentum_score": 60,
            "combined_score": 76, "position_weight_pct": 8,
            "thesis": "t", "key_risks": "r", "sharia_status": "compliant",
        }

    @patch("db.queries.get_client")
    def test_acted_on_true_is_preserved(self, mock_client):
        mc = MagicMock()
        mc.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[{"ticker": "AAPL", "acted_on": True}])
        mc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_client.return_value = mc

        from db.queries import save_watchlist
        save_watchlist(date(2026, 4, 28), [self._item("AAPL")])

        payload = mc.table.return_value.upsert.call_args[0][0]
        row = next(r for r in payload if r["ticker"] == "AAPL")
        self.assertTrue(row["acted_on"],
                        "acted_on=True must survive a watchlist refresh")

    @patch("db.queries.get_client")
    def test_new_ticker_defaults_acted_on_false(self, mock_client):
        mc = MagicMock()
        mc.table.return_value.select.return_value.eq.return_value.execute.return_value = \
            MagicMock(data=[])
        mc.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_client.return_value = mc

        from db.queries import save_watchlist
        save_watchlist(date(2026, 4, 28), [self._item("NVDA")])

        payload = mc.table.return_value.upsert.call_args[0][0]
        row = next(r for r in payload if r["ticker"] == "NVDA")
        self.assertFalse(row["acted_on"])


# ── 10. Technical indicator calculations ──────────────────────────────────────

class TestTechnicalIndicators(unittest.TestCase):

    def test_rsi_strong_uptrend_exceeds_78(self):
        from tools.technical import calculate_signals
        signals = calculate_signals([100.0 + i for i in range(210)])
        self.assertGreater(signals["rsi"], 78)

    def test_rsi_balanced_market_near_50(self):
        from tools.technical import calculate_signals
        # Alternating ±1 → 7 gains + 7 losses of equal size → RSI = 50
        prices = []
        p = 150.0
        for i in range(210):
            prices.append(p)
            p += 1.0 if i % 2 == 0 else -1.0
        signals = calculate_signals(prices)
        self.assertAlmostEqual(signals["rsi"], 50.0, delta=1.0)

    def test_ma200_extension_correct(self):
        from tools.technical import calculate_signals
        # 209 bars at $100, then $260 → MA200 ≈ $100.76 → extension > 150%
        signals = calculate_signals([100.0] * 209 + [260.0])
        self.assertGreater(signals["ma200_extension_pct"], 150)

    def test_above_flags_reflect_price(self):
        from tools.technical import calculate_signals
        closes = [100.0] * 210
        closes[-1] = 120.0
        signals = calculate_signals(closes)
        self.assertTrue(signals["above_ma50"])
        self.assertTrue(signals["above_ma200"])

    def test_empty_closes_returns_safe_defaults(self):
        from tools.technical import calculate_signals
        signals = calculate_signals([])
        self.assertEqual(signals["rsi"], 50.0)
        self.assertEqual(signals["current"], 0.0)

    def test_avg_volume_uses_20d_window(self):
        from tools.technical import calculate_signals
        volumes = [1_000] * 190 + [2_000] * 20
        signals = calculate_signals([100.0] * 210, volumes)
        self.assertAlmostEqual(signals["avg_vol_20"], 2_000.0)


if __name__ == "__main__":
    unittest.main()
