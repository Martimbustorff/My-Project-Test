"""
Symbol universes for research queries.
Claude picks which universe(s) to scan based on the user's natural-language query.
"""

UNIVERSES: dict[str, list[str]] = {
    "small_cap": [
        "SMCI","AEHR","BOOT","AXSM","ARQT","MARA","RIOT","CLSK","ASTS","RKLB",
        "IONQ","RCAT","LUNR","ACHR","JOBY","SOUN","KULR","BBAI","HIMS","RXRX",
        "PRCT","CERT","ARDX","AMRX","ACVA","NVTS","CLOV","SOFI","UPST","AFRM",
    ],
    "large_cap": [
        "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","BRK-B","JPM","V",
        "UNH","XOM","LLY","AVGO","MA","HD","CVX","MRK","ABBV","PEP",
        "KO","WMT","BAC","NFLX","ORCL","ADBE","CRM","ACN","TXN","QCOM",
    ],
    "tech": [
        "NVDA","AAPL","MSFT","AMD","AVGO","TSM","ASML","QCOM","MU","LRCX",
        "AMAT","KLAC","SNPS","CDNS","MRVL","ON","SMCI","ARM","PLTR","AI",
        "DDOG","SNOW","NET","CRWD","ZS","PANW","FTNT","OKTA","MDB","GTLB",
    ],
    "growth": [
        "NVDA","TSLA","META","AMZN","PLTR","MSTR","COIN","RKLB","ASTS","IONQ",
        "HOOD","SOFI","UPST","AFRM","HIMS","CELH","DUOL","APP","AXON","DDOG",
        "SNOW","NET","CRWD","ABNB","UBER","LYFT","RBLX","U","TTWO","EA",
    ],
    "value": [
        "BRK-B","JPM","BAC","WFC","C","GS","XOM","CVX","VZ","T",
        "IBM","INTC","PFE","MO","KO","PEP","WMT","TGT","HD","LOW",
        "MMM","CAT","DE","GE","HON","LMT","RTX","NOC","GD","BA",
    ],
    "crypto": [
        "BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD",
        "ADA-USD","AVAX-USD","DOT-USD","MATIC-USD","LINK-USD",
        "DOGE-USD","LTC-USD","ATOM-USD","UNI-USD","NEAR-USD",
    ],
    "healthcare": [
        "LLY","ABBV","MRK","JNJ","PFE","AMGN","GILD","REGN","VRTX","ISRG",
        "DXCM","IDXX","ALGN","HOLX","HIMS","RXRX","ARQT","AXSM","MRNA","BNTX",
    ],
    "energy": [
        "XOM","CVX","COP","EOG","SLB","MPC","PSX","VLO","OXY","HAL",
        "DVN","FANG","APA","CTRA","MRO","BP","SHEL","TTE","ENB","ET",
    ],
    "etf": [
        "SPY","QQQ","IWM","GLD","TLT","VTI","ARKK","SMH","XLK","XLF",
        "XLE","XLV","SOXX","GDX","SLV","USO","DBA","KWEB","EEM","VWO",
    ],
    "general": [
        "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","PLTR","AMD","COIN",
        "MSTR","SMCI","RKLB","ASTS","HIMS","SOFI","UPST","AXON","APP","DDOG",
        "BTC-USD","ETH-USD","SOL-USD","SPY","QQQ","AVGO","LLY","JPM","V","MA",
    ],
}


def get_symbols_for_query(intent: dict) -> list[str]:
    """Return a deduplicated symbol list based on parsed intent."""
    universes = intent.get("universes", ["general"])
    symbols: list[str] = []
    for u in universes:
        symbols.extend(UNIVERSES.get(u, []))
    # deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            result.append(s)
    max_sym = int(intent.get("max_symbols", 25))
    return result[:max_sym]
