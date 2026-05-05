"""Application configuration for the CGC arbitrage scanner."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path = Path(__file__).with_name(".env")) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv()

APP_NAME = "CGC Slab Arbitrage Scanner"
APP_DIR = Path(os.getenv("CGC_ARBITRAGE_APP_DIR", Path.home() / ".cgc_arbitrage"))
DATABASE_PATH = Path(os.getenv("CGC_ARBITRAGE_DB", APP_DIR / "scanner.sqlite3"))
PRESET_WATCHLIST_PATH = Path(
    os.getenv("CGC_PRESET_WATCHLIST", Path(__file__).with_name("liquid_titles.csv"))
)
LOCAL_FAIR_VALUES_PATH = Path(
    os.getenv("CGC_LOCAL_FAIR_VALUES", Path(__file__).with_name("fair_values.csv"))
)
MOCK_EBAY_LISTINGS_PATH = Path(
    os.getenv("CGC_MOCK_EBAY_LISTINGS", Path(__file__).with_name("mock_ebay_listings.csv"))
)


@dataclass(frozen=True)
class EbayConfig:
    mode: str = os.getenv("CGC_EBAY_MODE", "live").lower()
    mock_listings_path: Path = MOCK_EBAY_LISTINGS_PATH
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
