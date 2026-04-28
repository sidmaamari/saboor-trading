# S&P 500 + NASDAQ 100 investable universe for Saboor.
# A Claude-based sharia screener performs the primary compliance gate on this list.
# Sectors with known broad non-compliance (conventional banking, alcohol,
# tobacco, weapons, gambling) are excluded upfront to reduce unnecessary calls.

UNIVERSE = [
    # ── Technology ────────────────────────────────────────────────────────────
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "TSLA", "AMD", "INTC",
    "QCOM", "AVGO", "TXN", "MU", "AMAT", "LRCX", "KLAC", "ADI", "MCHP",
    "SWKS", "MPWR", "ON", "ENPH", "SEDG", "FSLR",
    "CRM", "ADBE", "ORCL", "NOW", "SNOW", "PLTR", "UBER", "ABNB", "SHOP",
    "TWLO", "ZM", "DOCU", "DDOG", "CRWD", "OKTA", "ZS", "NET", "HUBS",
    # FIX [HIGH H-13]: Removed DKNG (DraftKings) — gambling is non-sharia-compliant
    # and should never have entered the universe in the first place.
    "BILL", "GTLB", "MDB", "ESTC", "CFLT",

    # ── E-commerce / Consumer Tech ────────────────────────────────────────────
    "AMZN", "ETSY", "EBAY", "CHWY", "W", "CVNA", "CART",

    # ── Semiconductors / Hardware ─────────────────────────────────────────────
    "ARM", "SMCI", "DELL", "HPQ", "HPE", "KEYS", "TRMB", "ANSS", "CDNS",
    "SNPS",

    # ── Healthcare ────────────────────────────────────────────────────────────
    "UNH", "JNJ", "ABBV", "MRK", "PFE", "AMGN", "GILD", "ISRG", "BSX",
    "MDT", "SYK", "EW", "DXCM", "ILMN", "REGN", "BIIB", "MRNA", "VRTX",
    "ZTS", "TMO", "DHR", "A", "IQV", "WAT", "BIO", "IDXX", "ALGN", "HOLX",
    "PODD", "RMD", "GEHC", "HCA", "CNC", "MOH", "HUM", "CI", "ELV",
    "ACAD", "SRPT", "ALNY", "IONS", "BMRN",

    # ── Consumer Discretionary ────────────────────────────────────────────────
    "HD", "LOW", "TJX", "ROST", "ULTA", "NKE", "LULU", "RH", "TSCO",
    "CMG", "SBUX", "YUM", "DPZ", "WING", "QSR",
    "F", "GM", "TM", "RIVN", "LCID",

    # ── Consumer Staples ──────────────────────────────────────────────────────
    "WMT", "COST", "TGT", "KR", "SYY", "PG", "CL", "KMB", "CHD", "CLX",
    "EL", "COTY", "MNST", "KDP", "KO", "PEP",

    # ── Industrials ───────────────────────────────────────────────────────────
    "HON", "CAT", "DE", "EMR", "ETN", "ROK", "DOV", "ITW", "GE", "MMM",
    "FTV", "CARR", "OTIS", "XYL", "ROP", "IDEX", "AME", "LDOS", "CACI",
    "HUBB", "GNRC", "CPRT", "ODFL", "SAIA", "XPO", "CHRW",
    "FDX", "UPS",

    # ── Energy ────────────────────────────────────────────────────────────────
    "XOM", "CVX", "COP", "EOG", "SLB", "HAL", "DVN", "HES", "FANG",
    "MPC", "PSX", "VLO", "OKE", "KMI", "WMB",

    # ── Materials ─────────────────────────────────────────────────────────────
    "LIN", "APD", "SHW", "ECL", "FCX", "NEM", "ALB", "PPG", "EMN",
    "CF", "MOS", "NUE", "STLD", "RS",

    # ── Communication Services (non-media — Claude sharia screener reviews) ────
    "NFLX", "DIS", "TMUS", "T", "VZ", "CHTR", "CMCSA",
    "TTWO", "EA", "RBLX", "U",

    # ── Payment Networks (fee-based, often sharia-compliant) ─────────────────
    "V", "MA", "PYPL", "FI", "FIS", "GPN",

    # ── Real Assets / Infrastructure ──────────────────────────────────────────
    "AMT", "CCI", "SBAC",  # cell towers — Claude checks debt ratios

    # ── Other Large-Cap Quality ───────────────────────────────────────────────
    "SPGI", "MCO", "ICE", "MSCI", "VRSK",
]


def get_universe() -> list[str]:
    return list(UNIVERSE)
