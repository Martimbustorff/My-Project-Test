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

def to_markdown(wl: WeeklyWatchlist) -> str:
    """Render the watchlist as a Markdown document."""
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
        "Consensus | 3M Trend |\n"
        "|---|--------|------|--------|----------:|-------:|-------:|"
        "----------:|---------:|"
    )
    rows = [
        f"| {r.rank} | `{r.symbol}` | {r.name} | {r.region} | "
        f"{r.composite_score:.1f} | {r.upside_score:.0f} | {r.growth_score:.0f} | "
        f"{r.consensus_score:.0f} | {_fmt_pct(r.price_change_3m)} |"
        for r in recs
    ]
    return header + "\n" + "\n".join(rows)


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
