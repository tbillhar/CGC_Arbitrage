"""Valuation and arbitrage math."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import LOCAL_FAIR_VALUES_PATH, PRICING, PricingConfig


@dataclass(frozen=True)
class FairValue:
    title: str
    issue_number: str
    grade: float
    value: float
    source: str


@dataclass(frozen=True)
class DealMath:
    fair_value: float
    listing_price: float
    shipping_cost: float
    selling_fee_rate: float
    payment_fee_rate: float
    fixed_order_fee: float
    target_profit_margin: float
    max_buy_price: float
    estimated_profit: float
    estimated_margin: float
    is_candidate: bool


class LocalFairValueProvider:
    def __init__(self, path: Path = LOCAL_FAIR_VALUES_PATH) -> None:
        self.path = path
        self._values: dict[tuple[str, str, float], FairValue] | None = None

    def fetch_fair_value(self, title: str, issue_number: str, grade: float) -> Optional[FairValue]:
        values = self._load_values()
        exact_value = values.get(self._key(title, issue_number, grade))
        if exact_value is not None:
            return exact_value
        return self._interpolated_value(title, issue_number, grade, values)

    def upsert_fair_value(self, fair_value: FairValue) -> None:
        rows = self._fair_value_rows()
        target_key = self._key(fair_value.title, fair_value.issue_number, fair_value.grade)
        updated = False
        for row in rows:
            try:
                row_key = self._key(row["title"], row["issue_number"], float(row["grade"]))
            except (KeyError, TypeError, ValueError):
                continue
            if row_key == target_key:
                row["fair_value"] = f"{fair_value.value:g}"
                updated = True
                break

        if not updated:
            rows.append(
                {
                    "title": fair_value.title,
                    "issue_number": fair_value.issue_number,
                    "grade": f"{fair_value.grade:g}",
                    "fair_value": f"{fair_value.value:g}",
                }
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["title", "issue_number", "grade", "fair_value"])
            writer.writeheader()
            writer.writerows(rows)
        self._values = None

    def _load_values(self) -> dict[tuple[str, str, float], FairValue]:
        if self._values is not None:
            return self._values

        self._values = {}
        if not self.path.exists():
            return self._values

        required_columns = {"title", "issue_number", "grade", "fair_value"}
        with self.path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
                missing = ", ".join(sorted(required_columns - set(reader.fieldnames or [])))
                raise ValueError(f"Local fair-value file is missing required columns: {missing}")

            for line_number, row in enumerate(reader, start=2):
                title = (row.get("title") or "").strip()
                issue_number = (row.get("issue_number") or "").strip()
                if not title or not issue_number:
                    raise ValueError(
                        f"Local fair-value file row {line_number} must include title and issue_number."
                    )
                try:
                    grade = float(row["grade"])
                    value = float(row["fair_value"])
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"Local fair-value file row {line_number} contains invalid numeric values."
                    ) from error

                fair_value = FairValue(
                    title=title,
                    issue_number=issue_number,
                    grade=grade,
                    value=value,
                    source="local_csv",
                )
                self._values[self._key(title, issue_number, grade)] = fair_value

        return self._values

    def _key(self, title: str, issue_number: str, grade: float) -> tuple[str, str, float]:
        return (title.strip().casefold(), issue_number.strip().casefold(), round(grade, 1))

    def _fair_value_rows(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []

        with self.path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                return []
            required_columns = {"title", "issue_number", "grade", "fair_value"}
            if not required_columns.issubset(set(reader.fieldnames)):
                missing = ", ".join(sorted(required_columns - set(reader.fieldnames)))
                raise ValueError(f"Local fair-value file is missing required columns: {missing}")
            return [
                {
                    "title": row.get("title", ""),
                    "issue_number": row.get("issue_number", ""),
                    "grade": row.get("grade", ""),
                    "fair_value": row.get("fair_value", ""),
                }
                for row in reader
            ]

    def _interpolated_value(
        self,
        title: str,
        issue_number: str,
        grade: float,
        values: dict[tuple[str, str, float], FairValue],
    ) -> Optional[FairValue]:
        title_key = title.strip().casefold()
        issue_key = issue_number.strip().casefold()
        matching_values = sorted(
            (
                fair_value
                for key, fair_value in values.items()
                if key[0] == title_key and key[1] == issue_key
            ),
            key=lambda fair_value: fair_value.grade,
        )
        for lower, upper in zip(matching_values, matching_values[1:]):
            if lower.grade < grade < upper.grade:
                grade_span = upper.grade - lower.grade
                value_span = upper.value - lower.value
                interpolated = lower.value + ((grade - lower.grade) / grade_span) * value_span
                return FairValue(
                    title=lower.title,
                    issue_number=lower.issue_number,
                    grade=grade,
                    value=round(interpolated, 2),
                    source="local_csv_interpolated",
                )
        return None


def calculate_deal(
    fair_value: float,
    listing_price: float,
    target_profit_margin: float,
    pricing: PricingConfig = PRICING,
) -> DealMath:
    """Calculate max buy price and expected return for a slab listing."""

    total_fee_rate = pricing.selling_fee_rate + pricing.payment_fee_rate
    net_after_sale_costs = fair_value * (1 - total_fee_rate) - pricing.shipping_cost - pricing.fixed_order_fee
    max_buy_price = max(0.0, net_after_sale_costs * (1 - target_profit_margin))
    estimated_profit = net_after_sale_costs - listing_price
    estimated_margin = estimated_profit / listing_price if listing_price > 0 else 0.0

    return DealMath(
        fair_value=fair_value,
        listing_price=listing_price,
        shipping_cost=pricing.shipping_cost,
        selling_fee_rate=pricing.selling_fee_rate,
        payment_fee_rate=pricing.payment_fee_rate,
        fixed_order_fee=pricing.fixed_order_fee,
        target_profit_margin=target_profit_margin,
        max_buy_price=round(max_buy_price, 2),
        estimated_profit=round(estimated_profit, 2),
        estimated_margin=round(estimated_margin, 4),
        is_candidate=listing_price <= max_buy_price and fair_value > 0,
    )
