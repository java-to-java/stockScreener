"""Nifty50 constituent list.

NSE reshuffles the index twice a year (March / September), so any hardcoded
list will drift. ``SEED_CONSTITUENTS`` below is a reference snapshot -
correct as of early-2025 to the best of available knowledge - meant only to
make the rest of the pipeline runnable out of the box.

Before relying on this for real analysis, refresh it with::

    python -m src.fetch_constituents

which pulls the official list from NSE's archives CSV and writes
``data/nifty50_constituents.json``. ``load_constituents()`` below prefers
that refreshed file and only falls back to the seed list if it is missing.
"""
import csv
import io
import json
from dataclasses import dataclass, asdict

import config


@dataclass(frozen=True)
class Constituent:
    symbol: str       # NSE trading symbol, without the .NS suffix
    name: str
    sector: str

    @property
    def yf_ticker(self) -> str:
        """Yahoo Finance ticker for this NSE symbol."""
        return f"{self.symbol}.NS"


# Reference snapshot - see module docstring. Symbols are NSE trading symbols.
SEED_CONSTITUENTS = [
    Constituent("ADANIENT", "Adani Enterprises", "Metals & Mining"),
    Constituent("ADANIPORTS", "Adani Ports and Special Economic Zone", "Services"),
    Constituent("APOLLOHOSP", "Apollo Hospitals Enterprise", "Healthcare"),
    Constituent("ASIANPAINT", "Asian Paints", "Consumer Durables"),
    Constituent("AXISBANK", "Axis Bank", "Financial Services"),
    Constituent("BAJAJ-AUTO", "Bajaj Auto", "Automobile and Auto Components"),
    Constituent("BAJFINANCE", "Bajaj Finance", "Financial Services"),
    Constituent("BAJAJFINSV", "Bajaj Finserv", "Financial Services"),
    Constituent("BEL", "Bharat Electronics", "Capital Goods"),
    Constituent("BHARTIARTL", "Bharti Airtel", "Telecommunication"),
    Constituent("BRITANNIA", "Britannia Industries", "Fast Moving Consumer Goods"),
    Constituent("CIPLA", "Cipla", "Healthcare"),
    Constituent("COALINDIA", "Coal India", "Oil Gas & Consumable Fuels"),
    Constituent("DRREDDY", "Dr. Reddy's Laboratories", "Healthcare"),
    Constituent("EICHERMOT", "Eicher Motors", "Automobile and Auto Components"),
    Constituent("GRASIM", "Grasim Industries", "Construction Materials"),
    Constituent("HCLTECH", "HCL Technologies", "Information Technology"),
    Constituent("HDFCBANK", "HDFC Bank", "Financial Services"),
    Constituent("HDFCLIFE", "HDFC Life Insurance", "Financial Services"),
    Constituent("HEROMOTOCO", "Hero MotoCorp", "Automobile and Auto Components"),
    Constituent("HINDALCO", "Hindalco Industries", "Metals & Mining"),
    Constituent("HINDUNILVR", "Hindustan Unilever", "Fast Moving Consumer Goods"),
    Constituent("ICICIBANK", "ICICI Bank", "Financial Services"),
    Constituent("INDUSINDBK", "IndusInd Bank", "Financial Services"),
    Constituent("INFY", "Infosys", "Information Technology"),
    Constituent("ITC", "ITC", "Fast Moving Consumer Goods"),
    Constituent("JSWSTEEL", "JSW Steel", "Metals & Mining"),
    Constituent("KOTAKBANK", "Kotak Mahindra Bank", "Financial Services"),
    Constituent("LT", "Larsen & Toubro", "Construction"),
    Constituent("LTIM", "LTIMindtree", "Information Technology"),
    Constituent("M&M", "Mahindra & Mahindra", "Automobile and Auto Components"),
    Constituent("MARUTI", "Maruti Suzuki India", "Automobile and Auto Components"),
    Constituent("NESTLEIND", "Nestle India", "Fast Moving Consumer Goods"),
    Constituent("NTPC", "NTPC", "Power"),
    Constituent("ONGC", "Oil & Natural Gas Corporation", "Oil Gas & Consumable Fuels"),
    Constituent("POWERGRID", "Power Grid Corporation of India", "Power"),
    Constituent("RELIANCE", "Reliance Industries", "Oil Gas & Consumable Fuels"),
    Constituent("SBILIFE", "SBI Life Insurance", "Financial Services"),
    Constituent("SHRIRAMFIN", "Shriram Finance", "Financial Services"),
    Constituent("SBIN", "State Bank of India", "Financial Services"),
    Constituent("SUNPHARMA", "Sun Pharmaceutical Industries", "Healthcare"),
    Constituent("TATACONSUM", "Tata Consumer Products", "Fast Moving Consumer Goods"),
    Constituent("TATAMOTORS", "Tata Motors", "Automobile and Auto Components"),
    Constituent("TATASTEEL", "Tata Steel", "Metals & Mining"),
    Constituent("TCS", "Tata Consultancy Services", "Information Technology"),
    Constituent("TECHM", "Tech Mahindra", "Information Technology"),
    Constituent("TITAN", "Titan Company", "Consumer Durables"),
    Constituent("TRENT", "Trent", "Consumer Services"),
    Constituent("ULTRACEMCO", "UltraTech Cement", "Construction Materials"),
    Constituent("WIPRO", "Wipro", "Information Technology"),
]

assert len(SEED_CONSTITUENTS) == 50, "Nifty50 seed list must have exactly 50 entries"


def load_constituents() -> list[Constituent]:
    """Return the refreshed constituent list if available, else the seed list."""
    if config.CONSTITUENTS_FILE.exists():
        raw = json.loads(config.CONSTITUENTS_FILE.read_text())
        return [Constituent(**row) for row in raw]
    return list(SEED_CONSTITUENTS)


def parse_nse_csv(csv_text: str) -> list[Constituent]:
    """Parse NSE's ind_nifty50list.csv into Constituent records.

    Expected columns (as published by NSE): Company Name, Industry, Symbol, ...
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    out = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        name = (row.get("Company Name") or "").strip()
        sector = (row.get("Industry") or "").strip()
        if symbol:
            out.append(Constituent(symbol=symbol, name=name, sector=sector))
    return out


def save_constituents(constituents: list[Constituent]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.CONSTITUENTS_FILE.write_text(
        json.dumps([asdict(c) for c in constituents], indent=2)
    )
