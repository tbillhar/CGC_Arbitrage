"""Valuation and arbitrage math."""

from __future__ import annotations

from dataclasses import dataclass

from config import PRICING, PricingConfig


@dataclass(frozen=True)
class DealMath:
    fair_value: float
    listing_price: float
    shipping_cost: float
    selling_fee_rate: float
    payment_fee_rate: float
    target_profit_margin: float
    max_buy_price: float
    estimated_profit: float
    estimated_margin: float
    is_candidate: bool


def calculate_deal(
    fair_value: float,
    listing_price: float,
    target_profit_margin: float,
    pricing: PricingConfig = PRICING,
) -> DealMath:
    """Calculate max buy price and expected return for a slab listing."""

    total_fee_rate = pricing.selling_fee_rate + pricing.payment_fee_rate
    net_after_sale_costs = fair_value * (1 - total_fee_rate) - pricing.shipping_cost
    max_buy_price = max(0.0, net_after_sale_costs * (1 - target_profit_margin))
    estimated_profit = net_after_sale_costs - listing_price
    estimated_margin = estimated_profit / listing_price if listing_price > 0 else 0.0

    return DealMath(
        fair_value=fair_value,
        listing_price=listing_price,
        shipping_cost=pricing.shipping_cost,
        selling_fee_rate=pricing.selling_fee_rate,
        payment_fee_rate=pricing.payment_fee_rate,
        target_profit_margin=target_profit_margin,
        max_buy_price=round(max_buy_price, 2),
        estimated_profit=round(estimated_profit, 2),
        estimated_margin=round(estimated_margin, 4),
        is_candidate=listing_price <= max_buy_price and fair_value > 0,
    )
