"""
app/intelligence/recommendation/heuristics/decoy_upgrade.py
The Decoy Effect (Asymmetric Dominance & Upgrade Arbitrage)
- If a customer adds a base/medium item (e.g. Medium Fries @ ₹99), detects whether an immediate size/tier
  upgrade (e.g. King Fries @ ₹109 or Whopper Meal) has an irresistible asymmetric price delta (e.g. <= 20%).
- Prioritizes framing the upgrade as a high-utility "no-brainer".
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any
from app.domain.catalog.entities import MenuItem


class DecoyUpgradeAnalyzer:
    @staticmethod
    def find_decoy_opportunity(
        cart_item_name: str,
        cart_item_price: Decimal,
        candidate_items: list[MenuItem],
    ) -> dict[str, Any] | None:
        """
        Detects if any candidate represents an asymmetric size/tier upgrade for a cart item.
        """
        n_lower = cart_item_name.lower()
        if cart_item_price <= Decimal("0"):
            return None

        for cand in candidate_items:
            cand_name = cand.name.lower()
            cand_price = cand.price.amount if hasattr(cand.price, "amount") else Decimal(str(cand.price))

            # Match item family dynamically via root prefix (e.g. Fries -> Fries (King), Whopper -> Double Whopper)
            base_root = n_lower.split("(")[0].strip()
            cand_root = cand_name.split("(")[0].strip()
            is_same_family = (
                len(base_root) >= 4 and (base_root in cand_root or cand_root in base_root)
            )

            if is_same_family and cand_price > cart_item_price:
                price_delta = cand_price - cart_item_price
                ratio = float(price_delta / cart_item_price)

                # Asymmetric upgrade: <= 25% price increase
                if ratio <= 0.25:
                    return {
                        "base_item_name": cart_item_name,
                        "upgrade_item": cand,
                        "price_delta": float(price_delta),
                        "upgrade_ratio": ratio,
                        "ui_framing": f"Upgrade to {cand.name} for just +Rs.{price_delta:.0f}!",
                    }
        return None
