"""
app/intelligence/agent/psychology.py
Behavioral Consumer Psychology Engine for QSR Commercial Intelligence.

Implements established principles of consumer behavior and dining psychology:
1. Sensory Appetitive Framing (Wansink et al., Cornell Food Lab):
   Evocative language describing taste, temperature, and texture stimulates salivary
   pathways and elevates taste expectation by ~23%.
2. Hick's Law & Cognitive Load Relief:
   Reduces decision paralysis by narrowing choices to binary/trinary distinct pillars
   rather than overwhelming lists.
3. Anchoring & Framing Effect (Kahneman & Tversky):
   Frames price additions as customer savings/rewards ("Save ₹45 today") rather than
   incremental expense to neutralize loss aversion.
4. Reciprocal Empathy & Conversational Grounding:
   Instantly validates dietary preferences (pure veg / spicy / sugar-free) creating
   psychological safety and trust.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


SENSORY_ADJECTIVES = {
    # Burgers & Savory
    "whopper": "flame-grilled Whopper with juicy smoky patties",
    "crispy veg": "crispy spiced vegetable patty with creamy mayo",
    "paneer": "succulent royal cottage cheese grilled with herbs",
    "chicken": "crispy golden-fried tender chicken",
    "burger": "freshly toasted flame-grilled burger",
    # Sides
    "fries": "hot, golden-crispy fries",
    "peri peri": "crispy fries tossed in fiery peri-peri spice",
    "onion rings": "crunchy, golden-brown battered onion rings",
    "dip": "rich, velvety dipping sauce",
    # Drinks
    "cold coffee": "rich, chilled espresso blended with creamy milk",
    "iced latte": "smooth chilled espresso over silky cold milk",
    "coke": "bubbly, ice-cold Coca-Cola",
    "fizz": "tangy, sparkling fruit cooler",
    "drink": "chilled, refreshing beverage",
    # Desserts
    "sundae": "creamy vanilla soft-serve drizzled with warm Belgian chocolate",
    "chocolate": "warm, decadent chocolate fudge",
    "fusion": "velvety soft-serve swirled with crunchy cookie bites",
    "dessert": "sweet, velvety treat",
}


class PsychologyEngine:
    """
    Applies behavioral consumer psychology to conversational responses and recommendations.
    """

    @classmethod
    def get_sensory_cue(cls, item_name: str) -> str:
        name_lower = item_name.lower()
        for key, cue in SENSORY_ADJECTIVES.items():
            if key in name_lower:
                return cue
        return item_name

    @classmethod
    def frame_sensory(cls, item_name: str, action: str = "added") -> str:
        """
        Frames an item action with appetite-stimulating sensory language.
        """
        cue = cls.get_sensory_cue(item_name)
        if action == "added":
            return f"Delicious choice! I've added the {cue} to your cart."
        elif action == "recommend":
            return f"How about our {cue} today? It's freshly prepared and a guest favorite!"
        return f"Sure, selecting the {cue} for you."

    @classmethod
    def frame_upgrade_anchor(cls, burger_name: str, savings_amount: float = 45.0) -> str:
        """
        Applies anchoring by framing meal combos as customer savings rather than cost.
        """
        cue = cls.get_sensory_cue(burger_name)
        return (
            f"Great pick with the {cue}! You can make it a full meal with hot crispy fries "
            f"and a chilled drink—saving ₹{int(savings_amount)} today. Would you like to upgrade?"
        )

    @classmethod
    def formulate_binary_choice(cls, option_a: str, option_b: str, context: str = "") -> str:
        """
        Applies Hick's Law: Formulates a clean binary choice to prevent cognitive fatigue.
        """
        cue_a = cls.get_sensory_cue(option_a)
        cue_b = cls.get_sensory_cue(option_b)
        lead = f"To pair with your {context}, " if context else "Would you prefer "
        return f"{lead}something chilled like {cue_a}, or a hot crispy side like {cue_b}?"

    @classmethod
    def validate_dietary_preference(cls, preference: Optional[str]) -> Optional[str]:
        """
        Provides conversational validation and psychological safety for dietary identity.
        """
        if not preference:
            return None
        pref_clean = preference.lower().strip()
        if "veg" in pref_clean and "non" not in pref_clean:
            return "Got it! Keeping everything 100% pure vegetarian for you."
        elif "non" in pref_clean:
            return "Sure thing! Showing our hearty non-vegetarian favorites."
        elif "spicy" in pref_clean:
            return "Love the heat! Pulling up our boldest peri-peri and fiery items."
        return None
