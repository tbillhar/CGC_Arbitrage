from pathlib import Path

import pytest

from config import PricingConfig
from valuation import LocalFairValueProvider, calculate_deal


def test_calculate_deal_marks_profitable_candidate() -> None:
    pricing = PricingConfig(selling_fee_rate=0.10, payment_fee_rate=0.03, shipping_cost=20)

    deal = calculate_deal(1000, 650, 0.20, pricing)

    assert deal.max_buy_price == 680.0
    assert deal.estimated_profit == 200.0
    assert deal.estimated_margin == pytest.approx(0.3077)
    assert deal.is_candidate is True


def test_calculate_deal_rejects_listing_above_max_buy() -> None:
    pricing = PricingConfig(selling_fee_rate=0.10, payment_fee_rate=0.03, shipping_cost=20)

    deal = calculate_deal(1000, 725, 0.20, pricing)

    assert deal.max_buy_price == 680.0
    assert deal.is_candidate is False


def test_local_fair_value_provider_matches_case_insensitive_title(tmp_path: Path) -> None:
    values_file = tmp_path / "fair_values.csv"
    values_file.write_text(
        "title,issue_number,grade,fair_value\n"
        "Amazing Spider-Man,300,9.8,6500\n",
        encoding="utf-8",
    )

    fair_value = LocalFairValueProvider(values_file).fetch_fair_value("amazing spider-man", "300", 9.8)

    assert fair_value is not None
    assert fair_value.value == 6500
    assert fair_value.source == "local_csv"
