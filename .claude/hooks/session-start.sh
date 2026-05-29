#!/bin/bash
# .claude/hooks/session-start.sh
# -----------------------------------------------------------------------------
# SessionStart hook for Claude Code on the web.
#
# Installs the Python dependencies for the trading_bot project so the agent can
# run the test suite and, in particular, generate the weekly stock watchlist
# with live market data (yfinance) during a web session.
#
# Design notes:
#   * Runs only in the remote (web) environment — local sessions are untouched.
#   * Synchronous: the session waits until deps are ready (no race conditions).
#   * Idempotent: pip skips already-satisfied packages, so re-runs are cheap and
#     benefit from the container's post-hook caching.
#   * The heavy ML stack (torch/transformers, used only by the news-sentiment
#     analyzer) is installed best-effort and never blocks startup — the
#     watchlist and the full test suite do not depend on it.
# -----------------------------------------------------------------------------
set -euo pipefail

# Only run in Claude Code on the web; no-op locally.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  echo "session-start: not a remote session; skipping dependency install."
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

echo "session-start: installing trading_bot dependencies …"

PIP="python3 -m pip"
$PIP install --quiet --upgrade pip >/dev/null 2>&1 || true

# Core deps required for the watchlist generator + the test suite. These all
# ship as pure-Python / prebuilt wheels and install quickly and reliably.
$PIP install --quiet \
  "yfinance>=0.2.50" \
  "pandas>=2.2.0" \
  "numpy>=1.26.0" \
  "rich>=13.7.0" \
  "requests>=2.31.0" \
  "python-dotenv>=1.0.0" \
  "pytz>=2024.1" \
  "pytest>=8.0.0"

# Extras used only by the live trading engine (not by the watchlist or tests).
# Installed best-effort and grouped so that one unavailable wheel never blocks
# the others — or the session:
#   * scheduler/broker/ML utils → main.py live loop
#   * pandas-ta          → analysis/technical.py  (no py3.11 wheel for the pin)
#   * feedparser         → data/news_fetcher.py   (sgmllib3k build is fragile)
#   * torch/transformers → analysis/sentiment.py  (FinBERT, multi-GB)
$PIP install --quiet "APScheduler>=3.10.4" "scipy>=1.13.0" "scikit-learn>=1.4.0" \
  "alpaca-py>=0.38.0" "newsapi-python>=0.2.7" \
  || echo "session-start: WARNING — some live-engine extras were skipped."
$PIP install --quiet "pandas-ta>=0.3.14b" \
  || echo "session-start: WARNING — pandas-ta skipped (technical analysis only)."
$PIP install --quiet "feedparser>=6.0.11" \
  || echo "session-start: WARNING — feedparser skipped (RSS news only)."
$PIP install --quiet "torch>=2.2.0" "transformers>=4.40.0" \
  || echo "session-start: WARNING — torch/transformers skipped (news sentiment only)."

# Make the trading_bot package importable from the repo root in this session.
echo "export PYTHONPATH=\"${PROJECT_DIR}/trading_bot:\${PYTHONPATH:-}\"" >> "${CLAUDE_ENV_FILE:-/dev/null}"

echo "session-start: dependencies ready."
