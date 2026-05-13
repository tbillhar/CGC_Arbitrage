from pathlib import Path

import pytest

from config import PricingConfig
from valuation import LocalFairValueProvider, calculate_buy_target, calculate_deal


def test_calculate_deal_marks_profitable_candidate() -> None:
    pricing = PricingConfig(selling_fee_rate=0.10, payment_fee_rate=0.03, fixed_order_fee=0, shipping_cost=20)

    deal = calculate_deal(1000, 650, 0.20, pricing)

    assert deal.max_buy_price == 680.0
    assert deal.estimated_profit == 200.0
    assert deal.estimated_margin == pytest.approx(0.3077)
    assert deal.is_candidate is True


def test_calculate_deal_rejects_listing_above_max_buy() -> None:
    pricing = PricingConfig(selling_fee_rate=0.10, payment_fee_rate=0.03, fixed_order_fee=0, shipping_cost=20)

    deal = calculate_deal(1000, 725, 0.20, pricing)

    assert deal.max_buy_price == 680.0
    assert deal.is_candidate is False


def test_calculate_deal_subtracts_fixed_order_fee() -> None:
    pricing = PricingConfig(selling_fee_rate=0.1325, payment_fee_rate=0, fixed_order_fee=0.40, shipping_cost=18)

    deal = calculate_deal(1000, 675, 0.20, pricing)

    assert deal.max_buy_price == 679.28
    assert deal.estimated_profit == 174.10
    assert deal.is_candidate is True


def test_calculate_buy_target_returns_convention_buy_math() -> None:
    pricing = PricingConfig(selling_fee_rate=0.1325, payment_fee_rate=0, fixed_order_fee=0.40, shipping_cost=18)

    target = calculate_buy_target(1000, 0.20, pricing)

    assert target.net_after_sale_costs == 849.10
    assert target.max_buy_price == 679.28
    assert target.estimated_profit_at_max_buy == 169.82
    assert target.estimated_margin_at_max_buy == pytest.approx(0.25)


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


def test_local_fair_value_provider_interpolates_between_known_grades(tmp_path: Path) -> None:
    values_file = tmp_path / "fair_values.csv"
    values_file.write_text(
        "title,issue_number,grade,fair_value\n"
        "Amazing Spider-Man,121,5.0,700\n"
        "Amazing Spider-Man,121,6.0,900\n",
        encoding="utf-8",
    )

    fair_value = LocalFairValueProvider(values_file).fetch_fair_value("Amazing Spider-Man", "121", 5.5)

    assert fair_value is not None
    assert fair_value.value == 800
    assert fair_value.source == "local_csv_interpolated"


def test_local_fair_value_provider_upserts_new_value(tmp_path: Path) -> None:
    values_file = tmp_path / "fair_values.csv"
    provider = LocalFairValueProvider(values_file)

    provider.upsert_fair_value(
        fair_value=provider_value("X-Men", "4", 5.0, 1200),
    )

    fair_value = provider.fetch_fair_value("X-Men", "4", 5.0)
    assert fair_value is not None
    assert fair_value.value == 1200


def test_local_fair_value_provider_upserts_existing_value(tmp_path: Path) -> None:
    values_file = tmp_path / "fair_values.csv"
    values_file.write_text(
        "title,issue_number,grade,fair_value\n"
        "X-Men,4,5,1000\n",
        encoding="utf-8",
    )
    provider = LocalFairValueProvider(values_file)

    provider.upsert_fair_value(provider_value("X-Men", "4", 5.0, 1200))

    assert values_file.read_text(encoding="utf-8").count("X-Men,4,5,1200") == 1
    fair_value = provider.fetch_fair_value("X-Men", "4", 5.0)
    assert fair_value is not None
    assert fair_value.value == 1200


def provider_value(title: str, issue_number: str, grade: float, value: float):
    from valuation import FairValue

    return FairValue(title=title, issue_number=issue_number, grade=grade, value=value, source="gocollect")
