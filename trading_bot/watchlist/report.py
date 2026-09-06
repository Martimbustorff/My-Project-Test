"""
watchlist/report.py
--------------------
Render a :class:`WeeklyWatchlist` to Markdown (for files / PRs / email) and to
the terminal via Rich (falling back to plain text when Rich is unavailable).
"""

from __future__ import annotations

from typing import Optional

from .watchlist import WeeklyWatchlist, Recommendation


def _fmt_pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value * 100:+.1f}%"


def _fmt_price(value: Optional[float], currency: str = "") -> str:
    if value is None:
        return "—"
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "GBp": "p", "CHF": "CHF ",
           "DKK": "kr ", "SEK": "kr ", "NOK": "kr "}.get(currency, "")
    return f"{sym}{value:,.2f}"


def _rec_key(value: Optional[str]) -> str:
    return "—" if not value else value.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _changes_section(delta) -> str:
    """Render the week-over-week diff against the previous snapshot."""
    lines: list[str] = [
        f"## 🔁 What changed since {delta.previous_week_of}",
        "",
    ]

    if not delta.has_changes:
        lines.append("_No entries, exits or rank changes since the last run._")
        return "\n".join(lines)

    if delta.entered:
        lines.append(
            f"🟢 **Entered ({len(delta.entered)}):** "
            + ", ".join(f"`{s}`" for s in delta.entered)
        )
    if delta.exited:
        lines.append(
            f"🔴 **Dropped out ({len(delta.exited)}):** "
            + ", ".join(f"`{s}`" for s in delta.exited)
        )
    if delta.entered or delta.exited:
        lines.append("")

    movers = delta.biggest_moves()
    if movers:
        lines.append("**Biggest rank moves**")
        lines.append("")
        lines.append("| Symbol | Was | Now | Move |")
        lines.append("|--------|----:|----:|:-----|")
        for m in movers:
            arrow = "🔺" if m.delta > 0 else "🔻"
            lines.append(
                f"| `{m.symbol}` | {m.previous_rank} | {m.current_rank} | "
                f"{arrow} {abs(m.delta)} |"
            )

    return "\n".join(lines)


def to_markdown(wl: WeeklyWatchlist, delta=None) -> str:
    """
    Render the watchlist as a Markdown document.

    When *delta* (a :class:`history.WatchlistDelta`) is supplied, a
    week-over-week "what changed" section is included.
    """
    lines: list[str] = []
    lines.append(f"# 📈 Weekly Stock Watchlist — week of {wl.week_of}")
    lines.append("")
    lines.append(
        f"*Generated {wl.generated_at} · horizon ≤ {wl.horizon_days} days "
        f"(~{round(wl.horizon_days / 30)} months) · regions: {', '.join(wl.regions)}*"
    )
    lines.append("")
    lines.append(
        f"Screened **{wl.universe_size}** American & European candidates; "
        f"**{wl.qualified_count}** qualified as growing stocks. "
        "Each list below ranks the qualifiers by a different lens."
    )
    lines.append("")
    lines.append(
        "> ⚠️ **Not investment advice.** Generated automatically from public "
        "fundamental & analyst data for research/education only. Do your own "
        "due diligence."
    )
    lines.append("")

    if delta is not None:
        lines.append(_changes_section(delta))
        lines.append("")

    lines.append("## 🏆 Top Overall (composite)")
    lines.append(_overall_table(wl.top_overall))
    lines.append("")

    lines.append("## 🚀 Biggest Upside (analyst price target vs. price)")
    lines.append(_dimension_table(wl.by_upside, "Upside", "upside_score",
                                  lambda r: _fmt_pct(r.upside_pct)))
    lines.append("")

    lines.append("## 📊 Financial Growth History (revenue growth)")
    lines.append(_dimension_table(wl.by_growth, "Growth", "growth_score",
                                  lambda r: _fmt_pct(r.revenue_growth)))
    lines.append("")

    lines.append("## 👥 Analyst Consensus")
    lines.append(_dimension_table(wl.by_consensus, "Consensus", "consensus_score",
                                  lambda r: _rec_key(r.recommendation_key)))
    lines.append("")

    lines.append(_data_quality_section(wl))
    lines.append("")

    lines.append("---")
    lines.append(
        "*Scores are 0–100. Composite weighting: 40% upside · 35% growth · "
        "25% consensus. Source: yfinance (public data).*"
    )
    return "\n".join(lines)


def _overall_table(recs: list[Recommendation]) -> str:
    if not recs:
        return "_No qualifying stocks this week._"
    header = (
        "| # | Symbol | Name | Region | Composite | Upside | Growth | "
        "Consensus | 3M Trend | Data |\n"
        "|---|--------|------|--------|----------:|-------:|-------:|"
        "----------:|---------:|:----:|"
    )
    rows = [
        f"| {r.rank} | `{r.symbol}` | {r.name} | {r.region} | "
        f"{r.composite_score:.1f} | {r.upside_score:.0f} | {r.growth_score:.0f} | "
        f"{r.consensus_score:.0f} | {_fmt_pct(r.price_change_3m)} | "
        f"{_coverage_badge(r)} |"
        for r in recs
    ]
    return header + "\n" + "\n".join(rows)


def _coverage_badge(r: Recommendation) -> str:
    """Show how many of the three dimensions are backed by real data."""
    coverage = getattr(r, "data_coverage", 3)
    return "✅ 3/3" if coverage == 3 else f"⚠️ {coverage}/3"


def _data_quality_section(wl: WeeklyWatchlist) -> str:
    """
    Report data gaps explicitly.

    A dimension with no underlying data scores a neutral 50, which would
    otherwise be indistinguishable from a genuine middling reading. Anything
    resting on such a fallback — or missing entirely — is named here rather
    than quietly folded into the ranking.
    """
    lines: list[str] = ["## 🔍 Data quality", ""]

    seen: dict[str, list[str]] = {}
    for group in (wl.top_overall, wl.by_upside, wl.by_growth, wl.by_consensus):
        for r in group:
            missing = getattr(r, "missing_dimensions", []) or []
            if missing:
                seen.setdefault(r.symbol, missing)

    failed = getattr(wl, "failed_symbols", []) or []

    if not seen and not failed:
        lines.append(
            "✅ Every ranked name had real data for all three dimensions, and "
            "every screened ticker returned data."
        )
        return "\n".join(lines)

    if failed:
        lines.append(
            f"❌ **No data returned ({len(failed)}):** "
            + ", ".join(f"`{s}`" for s in failed)
            + " — excluded from the ranking entirely."
        )
        lines.append("")

    if seen:
        lines.append(
            "⚠️ **Scored on partial data** — the dimensions below had no "
            "underlying figures, so they fall back to a neutral 50 and their "
            "composite is less reliable than a full-coverage name:"
        )
        lines.append("")
        lines.append("| Symbol | Missing dimension(s) |")
        lines.append("|--------|----------------------|")
        for symbol in sorted(seen):
            lines.append(f"| `{symbol}` | {', '.join(seen[symbol])} |")

    return "\n".join(lines)


def _dimension_table(recs: list[Recommendation], label: str,
                     score_attr: str, detail_fn) -> str:
    if not recs:
        return "_No qualifying stocks this week._"
    header = (
        f"| # | Symbol | Name | Region | {label} Score | Detail | Price | Target |\n"
        "|---|--------|------|--------|------------:|-------:|------:|-------:|"
    )
    rows = []
    for r in recs:
        score = getattr(r, score_attr)
        rows.append(
            f"| {r.rank} | `{r.symbol}` | {r.name} | {r.region} | "
            f"{score:.0f} | {detail_fn(r)} | "
            f"{_fmt_price(r.current_price, r.currency)} | "
            f"{_fmt_price(r.target_mean_price, r.currency)} |"
        )
    return header + "\n" + "\n".join(rows)


# ---------------------------------------------------------------------------
# Terminal (Rich, with plain fallback)
# ---------------------------------------------------------------------------

def print_report(wl: WeeklyWatchlist) -> None:
    """Print the watchlist to the terminal (Rich if available, else plain)."""
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
    except ImportError:
        print(to_markdown(wl))
        return

    console = Console()
    console.print(
        f"\n[bold cyan]📈 Weekly Stock Watchlist[/bold cyan] — "
        f"week of [bold]{wl.week_of}[/bold]"
    )
    console.print(
        f"[dim]horizon ≤ {wl.horizon_days}d · regions {', '.join(wl.regions)} · "
        f"{wl.qualified_count}/{wl.universe_size} qualified[/dim]\n"
    )

    sections = [
        ("🏆 Top Overall (composite)", wl.top_overall, "composite_score", None),
        ("🚀 Biggest Upside", wl.by_upside, "upside_score",
         lambda r: _fmt_pct(r.upside_pct)),
        ("📊 Financial Growth", wl.by_growth, "growth_score",
         lambda r: _fmt_pct(r.revenue_growth)),
        ("👥 Analyst Consensus", wl.by_consensus, "consensus_score",
         lambda r: _rec_key(r.recommendation_key)),
    ]

    for title, recs, score_attr, detail_fn in sections:
        table = Table(title=title, box=box.SIMPLE_HEAVY, header_style="bold white",
                      title_style="bold yellow")
        table.add_column("#", justify="right", width=3)
        table.add_column("Symbol", style="bold cyan")
        table.add_column("Name")
        table.add_column("Region", justify="center", width=6)
        table.add_column("Score", justify="right")
        if detail_fn:
            table.add_column("Detail", justify="right")
        table.add_column("3M", justify="right")

        if not recs:
            console.print(f"[dim]{title}: no qualifying stocks this week.[/dim]")
            continue

        for r in recs:
            score = getattr(r, score_attr)
            row = [str(r.rank), r.symbol, r.name, r.region, f"{score:.0f}"]
            if detail_fn:
                row.append(detail_fn(r))
            trend = r.price_change_3m
            trend_str = _fmt_pct(trend)
            if trend is not None:
                trend_str = (f"[green]{trend_str}[/green]" if trend >= 0
                             else f"[red]{trend_str}[/red]")
            row.append(trend_str)
            table.add_row(*row)
        console.print(table)
        console.print()
