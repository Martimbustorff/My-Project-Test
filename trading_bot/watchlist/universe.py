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
    # Semiconductors / hardware
    Candidate("ARM",   "Arm Holdings",            "US", "Nasdaq"),
    Candidate("MU",    "Micron Technology",       "US", "Nasdaq"),
    Candidate("LRCX",  "Lam Research",            "US", "Nasdaq"),
    Candidate("KLAC",  "KLA Corporation",         "US", "Nasdaq"),
    Candidate("ANET",  "Arista Networks",         "US", "NYSE"),
    Candidate("SMCI",  "Super Micro Computer",    "US", "Nasdaq"),
    Candidate("VRT",   "Vertiv Holdings",         "US", "NYSE"),
    Candidate("CRDO",  "Credo Technology",        "US", "Nasdaq"),
    # Software / internet
    Candidate("APP",   "AppLovin",                "US", "Nasdaq"),
    Candidate("WDAY",  "Workday",                 "US", "Nasdaq"),
    Candidate("TEAM",  "Atlassian",               "US", "Nasdaq"),
    Candidate("HUBS",  "HubSpot",                 "US", "NYSE"),
    Candidate("FTNT",  "Fortinet",                "US", "Nasdaq"),
    Candidate("GTLB",  "GitLab",                  "US", "Nasdaq"),
    Candidate("S",     "SentinelOne",             "US", "NYSE"),
    Candidate("DASH",  "DoorDash",                "US", "Nasdaq"),
    Candidate("DUOL",  "Duolingo",                "US", "Nasdaq"),
    Candidate("TOST",  "Toast",                   "US", "NYSE"),
    # Fintech / consumer
    Candidate("HOOD",  "Robinhood Markets",       "US", "Nasdaq"),
    Candidate("COIN",  "Coinbase Global",         "US", "Nasdaq"),
    Candidate("CAVA",  "CAVA Group",              "US", "NYSE"),
    Candidate("ONON",  "On Holding",              "US", "NYSE"),
    Candidate("AXON",  "Axon Enterprise",         "US", "Nasdaq"),
    # Small-cap / emerging growth
    Candidate("SOFI",  "SoFi Technologies",       "US", "Nasdaq"),
    Candidate("AFRM",  "Affirm Holdings",         "US", "Nasdaq"),
    Candidate("IOT",   "Samsara",                 "US", "NYSE"),
    Candidate("ESTC",  "Elastic",                 "US", "NYSE"),
    Candidate("CELH",  "Celsius Holdings",        "US", "Nasdaq"),
    Candidate("RKLB",  "Rocket Lab",              "US", "Nasdaq"),
    Candidate("ASTS",  "AST SpaceMobile",         "US", "Nasdaq"),
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
    # Germany (Xetra) — large/mid
    Candidate("ALV.DE",   "Allianz",                 "EU", "Xetra"),
    Candidate("MBG.DE",   "Mercedes-Benz Group",     "EU", "Xetra"),
    Candidate("BMW.DE",   "BMW",                     "EU", "Xetra"),
    Candidate("BAS.DE",   "BASF",                    "EU", "Xetra"),
    Candidate("MRK.DE",   "Merck KGaA",              "EU", "Xetra"),
    Candidate("SY1.DE",   "Symrise",                 "EU", "Xetra"),
    # France (Euronext Paris) — large/mid
    Candidate("BNP.PA",   "BNP Paribas",             "EU", "Euronext Paris"),
    Candidate("CAP.PA",   "Capgemini",               "EU", "Euronext Paris"),
    Candidate("EL.PA",    "EssilorLuxottica",        "EU", "Euronext Paris"),
    Candidate("SAF.PA",   "Safran",                  "EU", "Euronext Paris"),
    Candidate("KER.PA",   "Kering",                  "EU", "Euronext Paris"),
    Candidate("DG.PA",    "Vinci",                   "EU", "Euronext Paris"),
    # UK (London Stock Exchange)
    Candidate("RR.L",     "Rolls-Royce Holdings",    "EU", "London Stock Exchange"),
    Candidate("GSK.L",    "GSK",                     "EU", "London Stock Exchange"),
    Candidate("ULVR.L",   "Unilever",                "EU", "London Stock Exchange"),
    Candidate("REL.L",    "RELX",                    "EU", "London Stock Exchange"),
    Candidate("HSBA.L",   "HSBC Holdings",           "EU", "London Stock Exchange"),
    Candidate("DGE.L",    "Diageo",                  "EU", "London Stock Exchange"),
    # Italy (Borsa Italiana)
    Candidate("RACE.MI",  "Ferrari",                 "EU", "Borsa Italiana"),
    Candidate("STLAM.MI", "Stellantis",              "EU", "Borsa Italiana"),
    Candidate("UCG.MI",   "UniCredit",               "EU", "Borsa Italiana"),
    # Spain (BME)
    Candidate("SAN.MC",   "Banco Santander",         "EU", "BME (Madrid)"),
    Candidate("BBVA.MC",  "BBVA",                    "EU", "BME (Madrid)"),
    Candidate("IBE.MC",   "Iberdrola",               "EU", "BME (Madrid)"),
    # Switzerland (SIX)
    Candidate("UBSG.SW",  "UBS Group",               "EU", "SIX Swiss Exchange"),
    Candidate("ROG.SW",   "Roche Holding",           "EU", "SIX Swiss Exchange"),
    Candidate("GIVN.SW",  "Givaudan",                "EU", "SIX Swiss Exchange"),
    # Netherlands / Belgium (Euronext)
    Candidate("HEIA.AS",  "Heineken",                "EU", "Euronext Amsterdam"),
    Candidate("WKL.AS",   "Wolters Kluwer",          "EU", "Euronext Amsterdam"),
    Candidate("BESI.AS",  "BE Semiconductor",        "EU", "Euronext Amsterdam"),
    Candidate("ABI.BR",   "Anheuser-Busch InBev",    "EU", "Euronext Brussels"),
    # Nordics
    Candidate("VOLV-B.ST","Volvo",                   "EU", "Nasdaq Stockholm"),
    Candidate("ATCO-A.ST","Atlas Copco",             "EU", "Nasdaq Stockholm"),
    Candidate("INVE-B.ST","Investor AB",             "EU", "Nasdaq Stockholm"),
    Candidate("NOVO-B.CO","Novo Nordisk (Copenhagen)", "EU", "Nasdaq Copenhagen"),
    Candidate("DSV.CO",   "DSV",                     "EU", "Nasdaq Copenhagen"),
    Candidate("EQNR.OL",  "Equinor",                 "EU", "Oslo Bors"),
    Candidate("NOKIA.HE", "Nokia",                   "EU", "Nasdaq Helsinki"),
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
