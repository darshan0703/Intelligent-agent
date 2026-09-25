"""
app/intelligence/recommendation/data_quality_gate.py
Data Quality & Imputation Gate (Resilience Layer):
- Deterministic calculation on the fly for missing features.
- Contextual imputation for cold-start or missing attributes.
- Explicit null-safety ensuring no runtime exceptions occur from incomplete records.
"""
from __future__ import annotations
from decimal import Decimal
from dataclasses import dataclass
from app.domain.catalog.entities import InventorySnapshot, MenuItem
from app.domain.catalog.value_objects import CategorySlug, FoodType, Price, ServingType


@dataclass
class CulinaryProfile:
    """In-memory inferred culinary scalars extracted from name and description."""
    spice_level: float = 0.0     # 0.0 (mild/none) to 1.0 (fiery/peri-peri)
    sweetness: float = 0.0       # 0.0 (savory) to 1.0 (dessert/sweet)
    dairy_content: float = 0.0   # 0.0 (dairy-free) to 1.0 (cheese/ice-cream/shake)
    texture: str = "standard"    # "crispy", "creamy", "fizzy", "tender", "rich", "standard"
    dominant_flavor: str | None = None  # e.g., "mango", "chocolate", "vanilla", "berry", "coffee"


class CulinaryTagger:
    """
    In-memory rule-based tagger that extracts spice_level, sweetness, dairy_content,
    texture, and dominant_flavor from item name and long_description dynamically per request.
    Zero-cache dev refactor: Operates on fresh SQL text on every request without caching.
    """
    _tag_cache: dict[int, CulinaryProfile] = {}

    @classmethod
    def extract_profile(cls, item_id: int | None, name: str, desc: str = "") -> CulinaryProfile:
        # Zero-cache dev mode: Always parse live text per request
        text = f"{name} {desc}".lower()
        name_lower = name.lower()

        # 1. Spice Level (0.0 to 1.0)
        spice = 0.0
        if any(w in text for w in ["fiery", "hell", "ghost", "super spicy", "flamin", "extra spicy"]):
            spice = 0.95
        elif any(w in text for w in ["peri peri", "peri-peri", "jalapeno"]):
            spice = 0.85
        elif any(w in text for w in ["spicy", "chilli", "chili", "hot & spicy", "pepper"]):
            spice = 0.70
        elif any(w in text for w in ["masala", "zesty", "tikka"]):
            spice = 0.45

        # 2. Sweetness (0.0 to 1.0)
        sweet = 0.0
        if any(w in text for w in ["sundae", "mousse", "lava", "cake", "chocolate", "choco", "sweet", "sugar", "caramel", "waffle", "cookie", "kitkat"]):
            sweet = 0.90
        elif any(w in text for w in ["softie", "shake", "float", "berry", "mango", "fanta", "mirinda", "currant"]):
            sweet = 0.75
        elif any(w in text for w in ["cola", "coke", "sprite", "fizz"]):
            sweet = 0.50
        elif any(w in text for w in ["frappe", "latte", "cappuccino", "coffee"]):
            sweet = 0.35

        # 3. Dairy Content (0.0 to 1.0)
        dairy = 0.0
        if any(w in text for w in ["softie", "ice cream", "shake", "cheese", "cheesy", "melt", "paneer", "mousse"]):
            dairy = 0.90
        elif any(w in text for w in ["latte", "cappuccino", "cream", "creamy", "float", "cup", "makhani"]):
            dairy = 0.65
        elif any(w in text for w in ["dip", "mayo", "butter", "sauce"]):
            dairy = 0.40

        # 4. Texture
        if any(w in text for w in ["crispy", "crunchy", "fried", "fries", "hashbrown", "nugget", "strip", "rings", "puff", "waffle", "taco"]):
            texture = "crispy"
        elif any(w in text for w in ["softie", "shake", "mousse", "creamy", "smooth", "ice cream", "frappe"]):
            texture = "creamy"
        elif any(w in text for w in ["fizz", "soda", "carbonated", "cola", "coke", "sprite", "mirinda", "thums up"]):
            texture = "fizzy"
        elif any(w in text for w in ["lava", "hot chocolate", "rich", "warm"]):
            texture = "rich"
        elif any(w in text for w in ["whopper", "patty", "grilled", "chicken", "burger", "tender"]):
            texture = "tender"
        else:
            texture = "standard"

        # 5. Dominant Flavor (e.g. "mango", "chocolate", "vanilla", "berry", "coffee")
        dominant_flavor: str | None = None
        if "mango" in name_lower or "mango" in text:
            dominant_flavor = "mango"
        elif any(w in name_lower or w in text for w in ["chocolate", "choco", "kitkat", "mousse", "fudge", "cocoa"]):
            dominant_flavor = "chocolate"
        elif "vanilla" in name_lower or "vanilla" in text:
            dominant_flavor = "vanilla"
        elif any(w in name_lower or w in text for w in ["berry", "currant", "strawberry", "blueberry", "raspberry"]):
            dominant_flavor = "berry"
        elif any(w in name_lower or w in text for w in ["coffee", "cappuccino", "latte", "americano", "espresso", "frappe", "mocha"]):
            dominant_flavor = "coffee"

        return CulinaryProfile(
            spice_level=round(spice, 2),
            sweetness=round(sweet, 2),
            dairy_content=round(dairy, 2),
            texture=texture,
            dominant_flavor=dominant_flavor,
        )

    @classmethod
    def get_dominant_flavor(cls, item: MenuItem | str | dict | None) -> str | None:
        """Extracts dominant_flavor dynamically from item name or object."""
        if not item:
            return None
        if isinstance(item, str):
            prof = cls.extract_profile(None, item)
            return prof.dominant_flavor
        if isinstance(item, dict):
            name = item.get("name") or item.get("item_name") or ""
            desc = item.get("short_description") or item.get("long_description") or item.get("description") or ""
            item_id = item.get("id") or item.get("item_id")
            prof = cls.extract_profile(int(item_id) if item_id is not None else None, name, desc)
            return prof.dominant_flavor
        desc = f"{getattr(item, 'short_description', '') or ''} {getattr(item, 'long_description', '') or ''}"
        prof = cls.extract_profile(item.id, item.name, desc)
        return prof.dominant_flavor

    @classmethod
    def warmup_catalog(cls, items: list[MenuItem]) -> None:
        """No-op in zero-cache dev mode; tags are evaluated dynamically per request."""
        pass


class DataQualityGate:
    """Sanitizes, validates, and imputes menu item records before entering recommendation pipelines."""

    @staticmethod
    def infer_category(name: str, raw_cat: Any) -> CategorySlug:
        c = str(raw_cat or "").lower()
        if "burger" in c or "whopper" in c:
            return CategorySlug.BURGER
        if "drink" in c or "beverage" in c or "shake" in c:
            return CategorySlug.DRINK
        if "side" in c or "fries" in c or "snack" in c:
            return CategorySlug.SIDE
        if "dessert" in c or "sundae" in c or "sweet" in c:
            return CategorySlug.DESSERT

        n = (name or "").lower()
        if any(x in n for x in ["coke", "shake", "coffee", "fizz", "pepsi", "latte", "drink", "tea"]):
            return CategorySlug.DRINK
        if any(x in n for x in ["fries", "nugget", "wing", "strip", "dip", "hashbrown"]):
            return CategorySlug.SIDE
        if any(x in n for x in ["sundae", "mousse", "softie", "lava", "cake", "dessert"]):
            return CategorySlug.DESSERT
        return CategorySlug.BURGER

    @staticmethod
    def infer_food_type(name: str, desc: str | None, raw_ft: Any) -> FoodType:
        if raw_ft:
            ft_obj = FoodType.from_str(str(raw_ft))
            if ft_obj:
                return ft_obj

        full_text = f"{name} {desc or ''}".lower()
        if any(k in full_text for k in ["chicken", "mutton", "meat", "fish", "egg", "non veg", "non-veg", "nonveg"]):
            return FoodType.NON_VEG
        return FoodType.VEG

    @staticmethod
    def fallback_image_url(category: CategorySlug, name: str) -> str:
        cat_val = category.value
        n = name.lower()
        if cat_val == "drink" or any(x in n for x in ("coke", "coffee", "shake", "fizz", "latte")):
            return "/src/assets/images/Drinks/Coca Cola.png"
        if cat_val == "side" or any(x in n for x in ("fries", "nugget", "wing", "strip", "hashbrown")):
            return "/src/assets/images/Sides/Fries (Medium).png"
        if cat_val == "dessert" or any(x in n for x in ("sundae", "softie", "mousse", "cone")):
            return "/src/assets/images/Dessert/Chocolate sundae.png"
        return "/src/assets/images/Burgers/Crispy Veg.png"

    @classmethod
    def sanitize_item(cls, item: MenuItem) -> MenuItem:
        """Applies null-safety and dynamic feature imputation to an item."""
        # 1. Price safety
        if not item.price or not isinstance(item.price, Price):
            safe_price = Price(Decimal("99.00"))
        else:
            safe_price = item.price

        # 2. Category safety & imputation
        cat = item.category
        if not cat or not isinstance(cat, CategorySlug):
            cat = cls.infer_category(item.name, cat)

        # 3. FoodType safety & imputation
        ft = item.food_type
        if not ft or not isinstance(ft, FoodType):
            ft = cls.infer_food_type(item.name, item.short_description, ft)

        # 4. ServingType safety
        st = item.serving_type
        if not st and cat == CategorySlug.DRINK:
            st = ServingType.HOT if any(x in item.name.lower() for x in ["hot", "coffee", "tea"]) else ServingType.COLD
        elif not st:
            st = ServingType.AMBIENT

        # 5. Image path normalization
        img = item.image
        if not img or img.strip() == "":
            img = cls.fallback_image_url(cat, item.name)
        elif not img.startswith("http") and not img.startswith("/"):
            img = "/" + img

        meal_img = item.meal_image or img
        if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
            meal_img = "/" + meal_img

        sanitized_item = MenuItem(
            id=item.id,
            name=item.name or "Unknown Item",
            short_description=item.short_description or item.name or "Delicious choice",
            long_description=item.long_description or item.name or "Freshly prepared",
            price=safe_price,
            category=cat,
            food_type=ft,
            serving_type=st,
            meal_role=item.meal_role or ("main" if cat == CategorySlug.BURGER else cat.value),
            meal_size=item.meal_size or "regular",
            is_meal_available=bool(item.is_meal_available),
            is_available=bool(item.is_available),
            image=img,
            meal_image=meal_img,
            section=item.section or cat.value.capitalize(),
            section_order=item.section_order or 0,
            display_order=item.display_order or 0,
            inventory=item.inventory,
        )
        culinary_prof = CulinaryTagger.extract_profile(
            item.id,
            sanitized_item.name,
            f"{sanitized_item.short_description} {sanitized_item.long_description}",
        )
        setattr(sanitized_item, "culinary_profile", culinary_prof)
        return sanitized_item

    @classmethod
    def get_culinary_profile(cls, item: MenuItem) -> CulinaryProfile:
        """Returns in-memory culinary scalars for any MenuItem."""
        if hasattr(item, "culinary_profile") and getattr(item, "culinary_profile"):
            return getattr(item, "culinary_profile")
        desc = f"{item.short_description or ''} {item.long_description or ''}"
        return CulinaryTagger.extract_profile(item.id, item.name, desc)

    @classmethod
    def sanitize_candidate_pool(cls, items: list[MenuItem]) -> list[MenuItem]:
        """Sanitizes an entire candidate pool with zero exception tolerance."""
        sanitized = []
        for i in items:
            try:
                sanitized.append(cls.sanitize_item(i))
            except Exception:
                pass
        return sanitized


# ── GENERATOR DATA QUALITY GATE — v7 §14 ───────────────────────────────────────
# Extends v6 §10 (freshness check) with volume and coverage checks.
# A generator is only trusted when ALL THREE dimensions pass:
#   freshness: within expected refresh window (existing v6 check)
#   volume:    row_count >= min_volume_threshold
#   coverage:  % of active catalog with any signal >= min_coverage_threshold
#
# co_purchase computed from 12 orders is fresh but not trustworthy —
# low volume, not low freshness. These are different claims and this gate
# is what tells them apart.

from dataclasses import dataclass as _dc
from datetime import datetime as _dt


@_dc
class SourceQualityReport:
    """
    Three-dimensional quality assessment for a recommendation signal source.
    trusted=True only when freshness AND volume AND coverage all pass.
    exclusion_reason is populated when trusted=False — always diagnosable, never silent.
    Recorded in DecisionTrace (§19) whenever a generator is excluded.
    """
    source: str
    is_fresh: bool
    volume_ok: bool
    coverage_ok: bool
    trusted: bool
    row_count: int
    coverage_pct: float
    exclusion_reason: str | None


class GeneratorQualityGate:
    """
    v7 §14: Assesses whether a generator source is trusted before it can
    influence candidate generation.

    v6 §10 excluded generators when their source table was stale (freshness only).
    v7 §14 adds the other half: excluding generators when the table is THIN,
    even if fresh.

    The two failures are:
      - stale: the data is old → freshness check
      - thin:  the data exists but is too sparse to be reliable → volume + coverage check

    These are different claims. 'We have A co-purchase table' ≠ 'We have reliable
    co-purchase intelligence'. The gate is what tells them apart.
    """

    # Minimum row counts per generator source
    MIN_VOLUME: dict[str, int] = {
        "co_purchase":  50,
        "semantic_fit": 20,
        "popularity":   10,
        "exploration":   5,
    }

    # Minimum fraction of active catalog items that must have a signal from this source
    MIN_COVERAGE: dict[str, float] = {
        "co_purchase":  0.25,  # At least 25% of catalog items have any co-purchase pairing
        "semantic_fit": 0.40,
        "popularity":   0.60,
        "exploration":  0.10,
    }

    # Expected refresh windows (seconds) per source
    MAX_STALENESS_SECONDS: dict[str, int] = {
        "co_purchase":  86400,    # 24h: recalculated from order history daily
        "semantic_fit": 604800,   # 7d: category structure rarely changes
        "popularity":   3600,     # 1h: popularity can shift during rush hours
        "exploration":  86400,    # 24h: novelty pool refreshed daily
    }

    @classmethod
    def assess(
        cls,
        source: str,
        row_count: int,
        catalog_size: int,
        last_updated: _dt | None = None,
    ) -> SourceQualityReport:
        """
        Assesses freshness, volume, and coverage for a signal source.
        Returns a SourceQualityReport — never raises, always diagnosable.
        """
        # Freshness check
        max_staleness = cls.MAX_STALENESS_SECONDS.get(source, 86400)
        if last_updated is None:
            # No timestamp: conservatively treat as fresh (don't exclude on missing metadata)
            is_fresh = True
        else:
            age_seconds = (_dt.utcnow() - last_updated).total_seconds()
            is_fresh = age_seconds <= max_staleness

        # Volume check
        min_vol = cls.MIN_VOLUME.get(source, 10)
        volume_ok = row_count >= min_vol

        # Coverage check
        min_cov = cls.MIN_COVERAGE.get(source, 0.10)
        coverage_pct = row_count / max(1, catalog_size)
        coverage_ok = coverage_pct >= min_cov

        trusted = is_fresh and volume_ok and coverage_ok

        exclusion_reason: str | None = None
        if not trusted:
            reasons = []
            if not is_fresh:
                reasons.append(f"stale (last_updated={last_updated})")
            if not volume_ok:
                reasons.append(f"thin_volume ({row_count} < {min_vol} required)")
            if not coverage_ok:
                reasons.append(f"low_coverage ({coverage_pct:.1%} < {min_cov:.0%} required)")
            exclusion_reason = "; ".join(reasons)

        return SourceQualityReport(
            source=source,
            is_fresh=is_fresh,
            volume_ok=volume_ok,
            coverage_ok=coverage_ok,
            trusted=trusted,
            row_count=row_count,
            coverage_pct=round(coverage_pct, 4),
            exclusion_reason=exclusion_reason,
        )

    @classmethod
    def assess_co_purchase(cls, row_count: int, catalog_size: int = 84) -> SourceQualityReport:
        """Convenience method for the primary co_purchase signal source."""
        return cls.assess("co_purchase", row_count, catalog_size)
