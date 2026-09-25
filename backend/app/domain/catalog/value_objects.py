"""
app/domain/catalog/value_objects.py
-------------------------------------
Catalog domain value objects.

RULES (enforced here):
- ALL monetary values use ``decimal.Decimal`` — never float.
- All classes are immutable (frozen dataclasses or plain classes with __slots__).
- Zero framework imports — pure Python stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

_TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Price:
    """Decimal-backed monetary value.

    All arithmetic produces a new ``Price`` — amounts are never mutated in place.

    Args:
        amount: The monetary amount as a ``Decimal``.  Strings and ints are
                accepted and coerced; floats are explicitly rejected.

    Raises:
        TypeError: If ``amount`` is a ``float`` (prevents precision loss).
        ValueError: If the resulting amount is negative.
    """

    amount: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.amount, float):
            raise TypeError(
                "Price.amount must be Decimal, not float.  "
                "Use Decimal('1.99') instead of 1.99."
            )
        # Coerce int / str to Decimal
        object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if self.amount < Decimal("0"):
            raise ValueError(f"Price cannot be negative: {self.amount}")

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def add(self, other: "Price") -> "Price":
        """Return a new Price equal to self + other."""
        return Price(self.amount + other.amount)

    def subtract(self, other: "Price") -> "Price":
        """Return a new Price equal to self - other (clamped to zero)."""
        result = self.amount - other.amount
        return Price(max(result, Decimal("0")))

    def multiply(self, factor: int | Decimal) -> "Price":
        """Return a new Price equal to self * factor.

        Args:
            factor: An integer or Decimal multiplier.  Float not accepted.
        """
        if isinstance(factor, float):
            raise TypeError("Multiplier must be int or Decimal, not float.")
        return Price(self.amount * Decimal(str(factor)))

    def round_to_cents(self) -> "Price":
        """Return a new Price rounded to 2 decimal places (HALF_UP)."""
        return Price(self.amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))

    # ------------------------------------------------------------------
    # Comparisons
    # ------------------------------------------------------------------

    def __lt__(self, other: "Price") -> bool:  # type: ignore[override]
        return self.amount < other.amount

    def __le__(self, other: "Price") -> bool:  # type: ignore[override]
        return self.amount <= other.amount

    def __gt__(self, other: "Price") -> bool:  # type: ignore[override]
        return self.amount > other.amount

    def __ge__(self, other: "Price") -> bool:  # type: ignore[override]
        return self.amount >= other.amount

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.amount:.2f}"

    def __repr__(self) -> str:
        return f"Price(amount=Decimal('{self.amount:.2f}'))"


ZERO_PRICE = Price(Decimal("0"))


# ---------------------------------------------------------------------------
# Item identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemId:
    """Strongly-typed item identifier backed by a positive integer."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int):
            raise TypeError(f"ItemId.value must be int, got {type(self.value).__name__}")
        if self.value <= 0:
            raise ValueError(f"ItemId must be a positive integer, got {self.value}")

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value


# ---------------------------------------------------------------------------
# Enumerations (str-backed for JSON serialisation compatibility)
# ---------------------------------------------------------------------------


class CategorySlug(str, Enum):
    """Valid product category slugs as stored in the database and used in URLs."""

    BURGER = "burger"
    DRINK = "drink"
    SIDE = "side"
    DESSERT = "dessert"
    COMBO = "combo"
    SAUCE = "sauce"
    BREAKFAST = "breakfast"
    SNACK = "snack"

    @classmethod
    def from_str(cls, value: str) -> "CategorySlug":
        """Case-insensitive lookup with a helpful error message."""
        try:
            return cls(value.lower().strip())
        except ValueError:
            valid = [m.value for m in cls]
            raise ValueError(
                f"Unknown category slug '{value}'.  Valid slugs: {valid}"
            ) from None


class FoodType(str, Enum):
    """Vegetarian classification of a menu item."""

    VEG = "veg"
    NON_VEG = "non_veg"

    @classmethod
    def from_str(cls, value: str | None) -> "FoodType | None":
        if value is None:
            return None
        norm = value.lower().replace(" ", "_").strip()
        try:
            return cls(norm)
        except ValueError:
            return None


class ServingType(str, Enum):
    """How the item is served at point of sale."""

    HOT = "hot"
    COLD = "cold"
    ICED = "iced"
    AMBIENT = "ambient"

    @classmethod
    def from_str(cls, value: str | None) -> "ServingType | None":
        if value is None:
            return None
        try:
            return cls(value.lower().strip())
        except ValueError:
            return None
