"""Application configuration for the CGC arbitrage scanner."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_NAME = "CGC Slab Arbitrage Scanner"
APP_DIR = Path(os.getenv("CGC_ARBITRAGE_APP_DIR", Path.home() / ".cgc_arbitrage"))
DATABASE_PATH = Path(os.getenv("CGC_ARBITRAGE_DB", APP_DIR / "scanner.sqlite3"))
PRESET_WATCHLIST_PATH = Path(
    os.getenv("CGC_PRESET_WATCHLIST", Path(__file__).with_name("liquid_titles.csv"))
)


@dataclass(frozen=True)
class EbayConfig:
    client_id: str = os.getenv("EBAY_CLIENT_ID", "")
    client_secret: str = os.getenv("EBAY_CLIENT_SECRET", "")
    marketplace_id: str = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US")
    browse_base_url: str = os.getenv(
        "EBAY_BROWSE_BASE_URL",
        "https://api.ebay.com/buy/browse/v1",
    )
    oauth_token_url: str = os.getenv(
        "EBAY_OAUTH_TOKEN_URL",
        "https://api.ebay.com/identity/v1/oauth2/token",
    )


@dataclass(frozen=True)
class GoCollectConfig:
    api_key: str = os.getenv("GOCOLLECT_API_KEY", "")
    base_url: str = os.getenv("GOCOLLECT_BASE_URL", "https://api.gocollect.com")


@dataclass(frozen=True)
class PricingConfig:
    selling_fee_rate: float = float(os.getenv("CGC_SELLING_FEE_RATE", "0.1325"))
    payment_fee_rate: float = float(os.getenv("CGC_PAYMENT_FEE_RATE", "0.03"))
    shipping_cost: float = float(os.getenv("CGC_SHIPPING_COST", "18.00"))
    default_profit_margin: float = float(os.getenv("CGC_DEFAULT_PROFIT_MARGIN", "0.20"))


EBAY = EbayConfig()
GOCOLLECT = GoCollectConfig()
PRICING = PricingConfig()
