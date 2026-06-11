"""
The watchlist: the stocks the scanner and the Trend Template tabs look at.

Each entry is:  "TICKER": ("Company name", "Sector")

Want to track different stocks? Just add or remove lines below — everything
else in the app updates automatically. Tickers must be the symbols Yahoo
Finance uses (e.g. "BRK-B" not "BRK.B").

The list mixes large, mid and small caps across Technology, Healthcare,
Energy, Financials, Consumer and Industrials, so the scanner sees a broad
slice of the US market (NYSE + Nasdaq).
"""

WATCHLIST = {
    # ------------------------- TECHNOLOGY -------------------------
    "AAPL":  ("Apple", "Technology"),
    "MSFT":  ("Microsoft", "Technology"),
    "NVDA":  ("NVIDIA", "Technology"),
    "GOOGL": ("Alphabet (Google)", "Technology"),
    "META":  ("Meta Platforms", "Technology"),
    "AVGO":  ("Broadcom", "Technology"),
    "ORCL":  ("Oracle", "Technology"),
    "CRM":   ("Salesforce", "Technology"),
    "ADBE":  ("Adobe", "Technology"),
    "AMD":   ("Advanced Micro Devices", "Technology"),
    "INTC":  ("Intel", "Technology"),
    "QCOM":  ("Qualcomm", "Technology"),
    "TXN":   ("Texas Instruments", "Technology"),
    "MU":    ("Micron Technology", "Technology"),
    "AMAT":  ("Applied Materials", "Technology"),
    "LRCX":  ("Lam Research", "Technology"),
    "KLAC":  ("KLA Corp", "Technology"),
    "ANET":  ("Arista Networks", "Technology"),
    "MRVL":  ("Marvell Technology", "Technology"),
    "ON":    ("ON Semiconductor", "Technology"),
    "NOW":   ("ServiceNow", "Technology"),
    "SNOW":  ("Snowflake", "Technology"),
    "PLTR":  ("Palantir", "Technology"),
    "NET":   ("Cloudflare", "Technology"),
    "DDOG":  ("Datadog", "Technology"),
    "CRWD":  ("CrowdStrike", "Technology"),
    "ZS":    ("Zscaler", "Technology"),
    "PANW":  ("Palo Alto Networks", "Technology"),
    "FTNT":  ("Fortinet", "Technology"),
    "OKTA":  ("Okta", "Technology"),
    "MDB":   ("MongoDB", "Technology"),
    "TWLO":  ("Twilio", "Technology"),
    "TEAM":  ("Atlassian", "Technology"),
    "U":     ("Unity Software", "Technology"),
    "RBLX":  ("Roblox", "Technology"),
    "SMCI":  ("Super Micro Computer", "Technology"),
    "DELL":  ("Dell Technologies", "Technology"),
    "HPQ":   ("HP Inc", "Technology"),
    "IBM":   ("IBM", "Technology"),
    "CSCO":  ("Cisco Systems", "Technology"),
    "INTU":  ("Intuit", "Technology"),
    "ADSK":  ("Autodesk", "Technology"),
    "SOUN":  ("SoundHound AI", "Technology"),
    "IONQ":  ("IonQ", "Technology"),
    "AI":    ("C3.ai", "Technology"),

    # ------------------------- HEALTHCARE -------------------------
    "UNH":   ("UnitedHealth Group", "Healthcare"),
    "JNJ":   ("Johnson & Johnson", "Healthcare"),
    "LLY":   ("Eli Lilly", "Healthcare"),
    "PFE":   ("Pfizer", "Healthcare"),
    "MRK":   ("Merck", "Healthcare"),
    "ABBV":  ("AbbVie", "Healthcare"),
    "TMO":   ("Thermo Fisher Scientific", "Healthcare"),
    "ABT":   ("Abbott Laboratories", "Healthcare"),
    "DHR":   ("Danaher", "Healthcare"),
    "BMY":   ("Bristol-Myers Squibb", "Healthcare"),
    "AMGN":  ("Amgen", "Healthcare"),
    "GILD":  ("Gilead Sciences", "Healthcare"),
    "VRTX":  ("Vertex Pharmaceuticals", "Healthcare"),
    "REGN":  ("Regeneron", "Healthcare"),
    "ISRG":  ("Intuitive Surgical", "Healthcare"),
    "MRNA":  ("Moderna", "Healthcare"),
    "BIIB":  ("Biogen", "Healthcare"),
    "CVS":   ("CVS Health", "Healthcare"),
    "CI":    ("Cigna", "Healthcare"),
    "HUM":   ("Humana", "Healthcare"),
    "ZTS":   ("Zoetis", "Healthcare"),
    "HCA":   ("HCA Healthcare", "Healthcare"),
    "MCK":   ("McKesson", "Healthcare"),
    "EXAS":  ("Exact Sciences", "Healthcare"),
    "CRSP":  ("CRISPR Therapeutics", "Healthcare"),
    "NVAX":  ("Novavax", "Healthcare"),

    # --------------------------- ENERGY ---------------------------
    "XOM":   ("Exxon Mobil", "Energy"),
    "CVX":   ("Chevron", "Energy"),
    "COP":   ("ConocoPhillips", "Energy"),
    "EOG":   ("EOG Resources", "Energy"),
    "SLB":   ("Schlumberger", "Energy"),
    "OXY":   ("Occidental Petroleum", "Energy"),
    "PSX":   ("Phillips 66", "Energy"),
    "MPC":   ("Marathon Petroleum", "Energy"),
    "VLO":   ("Valero Energy", "Energy"),
    "DVN":   ("Devon Energy", "Energy"),
    "HAL":   ("Halliburton", "Energy"),
    "FANG":  ("Diamondback Energy", "Energy"),
    "APA":   ("APA Corp", "Energy"),
    "AR":    ("Antero Resources", "Energy"),
    "FSLR":  ("First Solar", "Energy"),
    "ENPH":  ("Enphase Energy", "Energy"),
    "PLUG":  ("Plug Power", "Energy"),
    "RUN":   ("Sunrun", "Energy"),

    # ------------------------- FINANCIALS -------------------------
    "JPM":   ("JPMorgan Chase", "Financials"),
    "BAC":   ("Bank of America", "Financials"),
    "WFC":   ("Wells Fargo", "Financials"),
    "GS":    ("Goldman Sachs", "Financials"),
    "MS":    ("Morgan Stanley", "Financials"),
    "C":     ("Citigroup", "Financials"),
    "BLK":   ("BlackRock", "Financials"),
    "SCHW":  ("Charles Schwab", "Financials"),
    "AXP":   ("American Express", "Financials"),
    "V":     ("Visa", "Financials"),
    "MA":    ("Mastercard", "Financials"),
    "PYPL":  ("PayPal", "Financials"),
    "COIN":  ("Coinbase", "Financials"),
    "HOOD":  ("Robinhood", "Financials"),
    "SOFI":  ("SoFi Technologies", "Financials"),
    "AFRM":  ("Affirm", "Financials"),
    "ALLY":  ("Ally Financial", "Financials"),
    "KEY":   ("KeyCorp", "Financials"),
    "RF":    ("Regions Financial", "Financials"),
    "USB":   ("U.S. Bancorp", "Financials"),
    "PNC":   ("PNC Financial", "Financials"),
    "TFC":   ("Truist Financial", "Financials"),

    # ---------------------- CONSUMER CYCLICAL ----------------------
    "AMZN":  ("Amazon", "Consumer Cyclical"),
    "TSLA":  ("Tesla", "Consumer Cyclical"),
    "HD":    ("Home Depot", "Consumer Cyclical"),
    "MCD":   ("McDonald's", "Consumer Cyclical"),
    "NKE":   ("Nike", "Consumer Cyclical"),
    "SBUX":  ("Starbucks", "Consumer Cyclical"),
    "LOW":   ("Lowe's", "Consumer Cyclical"),
    "TGT":   ("Target", "Consumer Cyclical"),
    "LULU":  ("Lululemon", "Consumer Cyclical"),
    "CMG":   ("Chipotle", "Consumer Cyclical"),
    "DKNG":  ("DraftKings", "Consumer Cyclical"),
    "RCL":   ("Royal Caribbean", "Consumer Cyclical"),
    "CCL":   ("Carnival", "Consumer Cyclical"),
    "MAR":   ("Marriott", "Consumer Cyclical"),
    "BKNG":  ("Booking Holdings", "Consumer Cyclical"),
    "ETSY":  ("Etsy", "Consumer Cyclical"),
    "W":     ("Wayfair", "Consumer Cyclical"),
    "CHWY":  ("Chewy", "Consumer Cyclical"),
    "DIS":   ("Walt Disney", "Consumer Cyclical"),
    "NFLX":  ("Netflix", "Consumer Cyclical"),
    "ROKU":  ("Roku", "Consumer Cyclical"),
    "DG":    ("Dollar General", "Consumer Cyclical"),
    "DLTR":  ("Dollar Tree", "Consumer Cyclical"),

    # ---------------------- CONSUMER STAPLES ----------------------
    "WMT":   ("Walmart", "Consumer Staples"),
    "COST":  ("Costco", "Consumer Staples"),
    "PG":    ("Procter & Gamble", "Consumer Staples"),
    "KO":    ("Coca-Cola", "Consumer Staples"),
    "PEP":   ("PepsiCo", "Consumer Staples"),
    "PM":    ("Philip Morris", "Consumer Staples"),
    "MO":    ("Altria", "Consumer Staples"),
    "EL":    ("Estée Lauder", "Consumer Staples"),
    "CL":    ("Colgate-Palmolive", "Consumer Staples"),
    "KMB":   ("Kimberly-Clark", "Consumer Staples"),
    "GIS":   ("General Mills", "Consumer Staples"),
    "KR":    ("Kroger", "Consumer Staples"),

    # ------------------------- INDUSTRIALS -------------------------
    "BA":    ("Boeing", "Industrials"),
    "CAT":   ("Caterpillar", "Industrials"),
    "DE":    ("Deere & Co", "Industrials"),
    "HON":   ("Honeywell", "Industrials"),
    "GE":    ("GE Aerospace", "Industrials"),
    "MMM":   ("3M", "Industrials"),
    "LMT":   ("Lockheed Martin", "Industrials"),
    "RTX":   ("RTX Corp", "Industrials"),
    "NOC":   ("Northrop Grumman", "Industrials"),
    "GD":    ("General Dynamics", "Industrials"),
    "UPS":   ("United Parcel Service", "Industrials"),
    "FDX":   ("FedEx", "Industrials"),
    "UNP":   ("Union Pacific", "Industrials"),
    "CSX":   ("CSX Corp", "Industrials"),
    "DAL":   ("Delta Air Lines", "Industrials"),
    "UAL":   ("United Airlines", "Industrials"),
    "AAL":   ("American Airlines", "Industrials"),
    "LUV":   ("Southwest Airlines", "Industrials"),
    "EMR":   ("Emerson Electric", "Industrials"),
    "ETN":   ("Eaton", "Industrials"),
    "PH":    ("Parker Hannifin", "Industrials"),
    "ROK":   ("Rockwell Automation", "Industrials"),
    "URI":   ("United Rentals", "Industrials"),
    "PWR":   ("Quanta Services", "Industrials"),
    "AXON":  ("Axon Enterprise", "Industrials"),
    "JOBY":  ("Joby Aviation", "Industrials"),
    "ACHR":  ("Archer Aviation", "Industrials"),
}

# The sector ETF each sector is compared against in the "Market Context" check.
# An ETF is a fund that tracks a whole group of stocks, so it tells you how the
# stock's "neighbourhood" is doing today.
SECTOR_ETFS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
}
DEFAULT_MARKET_ETF = "SPY"  # fallback: the whole S&P 500


def all_tickers():
    """Return every ticker in the watchlist as a sorted list."""
    return sorted(WATCHLIST.keys())


def company_name(ticker):
    """Company name for a ticker (or the ticker itself if unknown)."""
    return WATCHLIST.get(ticker, (ticker, "Other"))[0]


def sector_of(ticker):
    """Sector for a ticker (or 'Other' if unknown)."""
    return WATCHLIST.get(ticker, (ticker, "Other"))[1]


def all_sectors():
    """Unique sector names present in the watchlist, sorted."""
    return sorted({s for _, s in WATCHLIST.values()})


# ---------------------------------------------------------------------------
# Helpers for the type-ahead stock search box (Analyse tab)
# ---------------------------------------------------------------------------

def ticker_options():
    """Searchable labels for every watchlist stock, e.g.
    'AAPL — Apple (Technology)'. Typing either the ticker OR the company
    name finds it."""
    return [f"{t} — {name} ({sector})"
            for t, (name, sector) in sorted(WATCHLIST.items())]


def option_label(ticker):
    """The search-box label for a ticker ('AAPL' -> 'AAPL — Apple (Technology)').
    Unknown tickers are returned as-is so any US stock can still be analysed."""
    t = (ticker or "").strip().upper()
    if t in WATCHLIST:
        name, sector = WATCHLIST[t]
        return f"{t} — {name} ({sector})"
    return t


def ticker_from_option(option):
    """Parse the ticker back out of a search-box value. Handles both picked
    options ('AAPL — Apple (Technology)') and free-typed text ('brk-b')."""
    if not option:
        return ""
    return option.split("—")[0].strip().upper()
