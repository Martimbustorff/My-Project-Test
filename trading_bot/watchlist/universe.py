"""
watchlist/universe.py
---------------------
The candidate universe screened for the weekly watchlist.

Scope (per requirements):
  * **American** stocks (NYSE / Nasdaq) and **European** stocks
    (LSE, Euronext, Xetra, SIX, Borsa Italiana, BME, OMX, etc.).
  * **Any market capitalisation** – large, mid and small caps are all eligible.

Tickers use the symbol format expected by yfinance: US tickers are bare
(``AAPL``), while European tickers carry their exchange suffix
(``ASML.AS``, ``SAP.DE``, ``MC.PA``, ``AZN.L`` …).

Each entry is a :class:`Candidate` carrying the metadata we cannot reliably
derive from the data provider (region + human-readable exchange).  The list is
intentionally broad and growth-tilted; the screener filters and ranks it down
to the weekly recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """A single screenable security."""

    symbol: str
    name: str
    region: str       # "US" | "EU"
    exchange: str     # human-readable venue


# ---------------------------------------------------------------------------
# American universe (NYSE / Nasdaq) — large, mid and small caps
# ---------------------------------------------------------------------------
_US: list[Candidate] = [
    # Mega / large-cap growth
    Candidate("NVDA",  "NVIDIA",                  "US", "Nasdaq"),
    Candidate("MSFT",  "Microsoft",               "US", "Nasdaq"),
    Candidate("AAPL",  "Apple",                   "US", "Nasdaq"),
    Candidate("AMZN",  "Amazon",                  "US", "Nasdaq"),
    Candidate("GOOGL", "Alphabet",                "US", "Nasdaq"),
    Candidate("META",  "Meta Platforms",          "US", "Nasdaq"),
    Candidate("AVGO",  "Broadcom",                "US", "Nasdaq"),
    Candidate("TSLA",  "Tesla",                   "US", "Nasdaq"),
    Candidate("LLY",   "Eli Lilly",               "US", "NYSE"),
    Candidate("V",     "Visa",                    "US", "NYSE"),
    Candidate("ORCL",  "Oracle",                  "US", "NYSE"),
    Candidate("CRM",   "Salesforce",              "US", "NYSE"),
    Candidate("AMD",   "Advanced Micro Devices",  "US", "Nasdaq"),
    Candidate("NFLX",  "Netflix",                 "US", "Nasdaq"),
    Candidate("ADBE",  "Adobe",                   "US", "Nasdaq"),
    Candidate("COST",  "Costco",                  "US", "Nasdaq"),
    Candidate("NOW",   "ServiceNow",              "US", "NYSE"),
    Candidate("INTU",  "Intuit",                  "US", "Nasdaq"),
    Candidate("QCOM",  "Qualcomm",                "US", "Nasdaq"),
    Candidate("AMAT",  "Applied Materials",       "US", "Nasdaq"),
    # Mid-cap growth
    Candidate("PLTR",  "Palantir Technologies",   "US", "NYSE"),
    Candidate("SNOW",  "Snowflake",               "US", "NYSE"),
    Candidate("DDOG",  "Datadog",                 "US", "Nasdaq"),
    Candidate("CRWD",  "CrowdStrike",             "US", "Nasdaq"),
    Candidate("NET",   "Cloudflare",              "US", "NYSE"),
    Candidate("SHOP",  "Shopify",                 "US", "NYSE"),
    Candidate("UBER",  "Uber Technologies",       "US", "NYSE"),
    Candidate("ABNB",  "Airbnb",                  "US", "Nasdaq"),
    Candidate("PANW",  "Palo Alto Networks",      "US", "Nasdaq"),
    Candidate("MELI",  "MercadoLibre",            "US", "Nasdaq"),
    Candidate("MDB",   "MongoDB",                 "US", "Nasdaq"),
    Candidate("ZS",    "Zscaler",                 "US", "Nasdaq"),
    Candidate("TTD",   "The Trade Desk",          "US", "Nasdaq"),
    Candidate("DKNG",  "DraftKings",              "US", "Nasdaq"),
    Candidate("RBLX",  "Roblox",                  "US", "NYSE"),
    # Small-cap / emerging growth
    Candidate("SOFI",  "SoFi Technologies",       "US", "Nasdaq"),
    Candidate("AFRM",  "Affirm Holdings",         "US", "Nasdaq"),
    Candidate("IOT",   "Samsara",                 "US", "NYSE"),
    Candidate("ESTC",  "Elastic",                 "US", "NYSE"),
    Candidate("CELH",  "Celsius Holdings",        "US", "Nasdaq"),
]

# ---------------------------------------------------------------------------
# European universe — large, mid and small caps across major venues
# ---------------------------------------------------------------------------
_EU: list[Candidate] = [
    # Large-cap
    Candidate("ASML.AS",  "ASML Holding",            "EU", "Euronext Amsterdam"),
    Candidate("SAP.DE",   "SAP",                     "EU", "Xetra"),
    Candidate("MC.PA",    "LVMH",                    "EU", "Euronext Paris"),
    Candidate("NVO",      "Novo Nordisk",            "EU", "NYSE (ADR) / Copenhagen"),
    Candidate("AZN.L",    "AstraZeneca",             "EU", "London Stock Exchange"),
    Candidate("SHEL.L",   "Shell",                   "EU", "London Stock Exchange"),
    Candidate("SIE.DE",   "Siemens",                 "EU", "Xetra"),
    Candidate("OR.PA",    "L'Oreal",                 "EU", "Euronext Paris"),
    Candidate("AIR.PA",   "Airbus",                  "EU", "Euronext Paris"),
    Candidate("SU.PA",    "Schneider Electric",      "EU", "Euronext Paris"),
    Candidate("RMS.PA",   "Hermes",                  "EU", "Euronext Paris"),
    Candidate("ISP.MI",   "Intesa Sanpaolo",         "EU", "Borsa Italiana"),
    Candidate("ITX.MC",   "Inditex",                 "EU", "BME (Madrid)"),
    Candidate("NESN.SW",  "Nestle",                  "EU", "SIX Swiss Exchange"),
    Candidate("NOVN.SW",  "Novartis",                "EU", "SIX Swiss Exchange"),
    Candidate("ADYEN.AS", "Adyen",                   "EU", "Euronext Amsterdam"),
    Candidate("PRX.AS",   "Prosus",                  "EU", "Euronext Amsterdam"),
    Candidate("DTE.DE",   "Deutsche Telekom",        "EU", "Xetra"),
    Candidate("ENEL.MI",  "Enel",                    "EU", "Borsa Italiana"),
    Candidate("SAN.PA",   "Sanofi",                  "EU", "Euronext Paris"),
    # Mid-cap growth
    Candidate("RHM.DE",   "Rheinmetall",             "EU", "Xetra"),
    Candidate("STMPA.PA", "STMicroelectronics",      "EU", "Euronext Paris"),
    Candidate("IFX.DE",   "Infineon Technologies",   "EU", "Xetra"),
    Candidate("ZAL.DE",   "Zalando",                 "EU", "Xetra"),
    Candidate("ERIC-B.ST","Ericsson",                "EU", "Nasdaq Stockholm"),
    Candidate("NDA-FI.HE","Nordea Bank",             "EU", "Nasdaq Helsinki"),
    Candidate("DSY.PA",   "Dassault Systemes",       "EU", "Euronext Paris"),
    Candidate("WISE.L",   "Wise",                    "EU", "London Stock Exchange"),
    Candidate("EVO.ST",   "Evolution AB",            "EU", "Nasdaq Stockholm"),
    Candidate("GFC.PA",   "Gecina",                  "EU", "Euronext Paris"),
    # Small-cap / emerging growth
    Candidate("ARGX.BR",  "argenx",                  "EU", "Euronext Brussels"),
    Candidate("TEP.PA",   "Teleperformance",         "EU", "Euronext Paris"),
    Candidate("SOON.SW",  "Sonova",                  "EU", "SIX Swiss Exchange"),
    Candidate("BC8.DE",   "Bechtle",                 "EU", "Xetra"),
    Candidate("BOSS.DE",  "Hugo Boss",               "EU", "Xetra"),
]


def default_universe() -> list[Candidate]:
    """Return the full American + European candidate universe."""
    return list(_US) + list(_EU)


def us_universe() -> list[Candidate]:
    """Return only the American candidates."""
    return list(_US)


def eu_universe() -> list[Candidate]:
    """Return only the European candidates."""
    return list(_EU)


def universe_for_regions(regions: list[str]) -> list[Candidate]:
    """
    Return candidates filtered to *regions* (e.g. ``["US", "EU"]``).

    Unknown region codes are ignored; an empty/unknown selection falls back
    to the full universe so callers never get an empty screen by accident.
    """
    wanted = {r.upper() for r in regions}
    selected = [c for c in default_universe() if c.region in wanted]
    return selected or default_universe()
