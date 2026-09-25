"""
app/intelligence/agent/cashier_agent.py
Autonomous, tool-grounded LangChain conversational cashier agent with Consumer Psychology.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.domain.session.entities import ConversationTurn, SessionState
from app.intelligence.agent.psychology import PsychologyEngine
from app.intelligence.agent.tools.catalog_tools import CatalogTools
from app.intelligence.agent.tools.screen_tools import ScreenTools
from app.ports.catalog_port import CatalogRepository
from app.ports.llm_port import LanguageModelPort
from app.ports.recommendation_port import RecommendationEngine
from app.observability.logging import get_logger

logger = get_logger(__name__)


class CashierDecision(BaseModel):
    intent: Literal[
        "open_category",
        "filter_menu",
        "add_to_cart",
        "remove_from_cart",
        "recommend",
        "screen_action",
        "checkout",
        "customize_burger",
        "clarify",
        "chit_chat",
    ] = Field(
        default="chit_chat",
        description="The primary action intended by the customer."
    )
    customization_action: Optional[Literal["split_burger", "swap_patty", "remove_topping", "add_topping", "reassemble"]] = Field(
        default=None,
        description="Burger customization action if customer mentions modifying ingredients or swapping patties."
    )
    customization_target: Optional[str] = Field(
        default=None,
        description="Target ingredient or patty (e.g. 'paneer', 'chicken', 'veg', 'double', 'cheese', 'onion', 'lettuce')."
    )
    target_item: Optional[str] = Field(
        default=None,
        description="Exact or referenced menu item name (e.g., 'Whopper', 'Classic Cold Coffee', 'Peri Peri Fries')."
    )
    category: Optional[Literal["burger", "drink", "side", "dessert"]] = Field(
        default=None,
        description="Target category if customer wants to browse or filter."
    )
    quantity: int = Field(
        default=1,
        description="Quantity of items to add or remove."
    )
    preference: Optional[Literal["veg", "non_veg", "both", "spicy"]] = Field(
        default=None,
        description="Customer dietary or taste preference if detected (veg, non_veg, both, spicy)."
    )
    spoken_message: str = Field(
        description="The customer-facing spoken response. Must apply sensory framing (e.g. 'flame-grilled Whopper', 'hot crispy fries') and conversational warmth. NO markdown, bullets, or asterisks."
    )
    ui_action: Optional[str] = Field(
        default=None,
        description="UI control or action name to dispatch on the kiosk screen."
    )
    ui_action_value: Optional[Any] = Field(
        default=None,
        description="Parameter value for the UI action (e.g. category name, filter name, or customization dict)."
    )
    psychological_principle_applied: Optional[str] = Field(
        default=None,
        description="Psychology principle leveraged: sensory_framing, hicks_binary_choice, savings_anchoring, reciprocal_warmth."
    )
    reasoning: str = Field(
        default="",
        description="Internal rationale explaining the decision."
    )


@dataclass
class AgentResponse:
    spoken_message: str
    ui_action: str | None = None
    ui_action_value: str | None = None
    target_screen: str | None = None
    decision: CashierDecision | None = None


class CashierAgent:
    def __init__(
        self,
        llm: LanguageModelPort,
        catalog: CatalogRepository,
        rec_engine: RecommendationEngine,
    ):
        self.llm = llm
        self.catalog = catalog
        self.rec_engine = rec_engine
        self.catalog_tools = CatalogTools(catalog, rec_engine)
        self.screen_tools = ScreenTools()
        self.psychology = PsychologyEngine()

    def _build_system_prompt(self, session: SessionState) -> str:
        pref_text = f"Customer Preference: {session.food_preference}" if session.food_preference else "Customer Preference: Not specified"
        screen_text = f"Current Screen: {session.current_screen.name}" if session.current_screen else "Current Screen: Home"
        last_cat = f"Last Viewed Category: {session.last_category}" if session.last_category else ""

        return f"""You are the intelligent, highly capable conversational cashier for Burger King India.
You understand natural English, Hinglish ("ek veg whopper dena", "kuch thanda pila do", "spicy fries add kar do", "kitna hua", "payment karna hai"), and everyday dining idioms.

ACTIVE KIOSK CONTEXT:
{screen_text}
{pref_text}
{last_cat}

BEHAVIORAL CONSUMER PSYCHOLOGY DIRECTIVES:
1. SENSORY APPETITIVE FRAMING: Always use mouthwatering, evocative sensory words when naming food:
   - Burgers: "flame-grilled", "freshly toasted", "juicy smoky patties"
   - Fries/Sides: "hot golden-crispy fries", "freshly tossed peri-peri fries", "crunchy onion rings"
   - Drinks: "ice-cold bubbly Coke", "rich chilled espresso Cold Coffee", "sparkling fruity fizz"
   - Desserts: "creamy vanilla soft-serve with warm Belgian chocolate drizzle"
2. HICK'S LAW (COGNITIVE RELIEF): If the customer is undecided or asks for suggestions, present at most 2 distinct choices (e.g. "Would you prefer a chilled Cold Coffee or hot crispy Peri Peri Fries with that?"). Never dump an overwhelming list of items.
3. SAVINGS ANCHORING: If the customer adds a burger, mention they can make it a full meal combo with fries and a drink to save ₹45 today!
4. RECIPROCAL WARMTH: Always validate their dietary choices ("Got it, keeping everything 100% pure vegetarian for you!").
5. SPOKEN CONVERSATIONAL TONE: Responses will be read aloud through the kiosk audio. Never use markdown, bullets, asterisks, or internal technical terms. Keep it to 1-2 friendly, natural sentences.

INTENT MAPPING RULES:
- DIETARY & LIFESTYLE FLOWS:
  - Vegetarian / Plant-based / Green mark:
    - "show me vegetarian" / "I only eat veg" / "I'm vegetarian" / "pure veg options" / "no meat" / "I don't eat chicken" / "no non-veg" / "green dot items" / "plant-based only" / "kuch veg dikhao" / "shakahari khana" / "sirf veg chahiye" / "bhai veg me kya hai" / "non-veg nahi khata" / "is there anything without meat" / "veg only" / "filter veg"
    -> If burgers mentioned ("veg burger", "vegetarian burgers", "plant based burger"):
       intent="open_category", category="burger", preference="veg", ui_action="filter_veg", spoken_message="Opening our 100% pure vegetarian flame-grilled burgers for you!"
    -> Otherwise:
       intent="filter_menu", preference="veg", ui_action="filter_veg", spoken_message="Filtering our 100% pure vegetarian menu for you! Everything is prepared with fresh greens and crispy plant-based goodness."
  - Non-Vegetarian / Meat / Chicken:
    - "show me non-veg" / "chicken options" / "chicken burgers" / "meat lovers" / "red dot items" / "kuch non veg dikhao" / "chicken wala kya hai" / "filter non-veg" / "juicy chicken"
    -> If burgers mentioned:
       intent="open_category", category="burger", preference="non_veg", ui_action="filter_non_veg", spoken_message="Showing our succulent, flame-grilled chicken burgers for you!"
    -> Otherwise:
       intent="filter_menu", preference="non_veg", ui_action="filter_non_veg", spoken_message="Showing our succulent, flame-grilled chicken and non-veg favorites for you!"
  - Reset / Show All / Both:
    - "show all" / "show both" / "everything" / "clear filter" / "remove filter" / "sab dikhao" / "dono dikhao"
    -> intent="filter_menu", preference="both", ui_action="filter_both", spoken_message="Showing our full menu with both pure veg and flame-grilled non-veg selections."
- INDIRECT & COLLOQUIAL INTENT FLOWS:
  - Thirst / Cold drinks: "I'm thirsty", "throat is dry", "kuch thanda peene ko do", "need something cold", "cold drink chahiye" -> intent="open_category", category="drink", ui_action="open_category", ui_action_value="drink"
  - Quick bites / Munchies: "need a quick snack", "something crunchy", "chota mota snack", "munchies", "kuch crunchy" -> intent="open_category", category="side", ui_action="open_category", ui_action_value="side"
  - Sweet tooth: "sweet tooth", "kuch meetha ho jaye", "ice cream khani hai", "sweet treat" -> intent="open_category", category="dessert", ui_action="open_category", ui_action_value="dessert"
  - Undecided / Recommendations: "what's your best seller?", "what do you recommend?", "kuch accha batao", "what's good here?", "kya special hai" -> intent="recommend", ui_action="get_recommendations"
  - Hungry / Big meal: "I'm starving", "pet bhar ke khana", "bada burger do", "heavy meal" -> intent="add_to_cart", target_item="Whopper Deluxe"
- DIRECT CATEGORIES & ITEMS:
  - "I want a burger" / "show me burgers" / "burger dikhao" -> intent="open_category", category="burger", ui_action="open_category", ui_action_value="burger"
  - "show me drinks" / "kuch thanda" / "beverages" -> intent="open_category", category="drink", ui_action="open_category", ui_action_value="drink"
  - "sides" / "fries chahiye" -> intent="open_category", category="side", ui_action="open_category", ui_action_value="side"
  - "dessert" / "ice cream" / "meetha" -> intent="open_category", category="dessert", ui_action="open_category", ui_action_value="dessert"
  - Specific item mentioned ("give me a whopper", "add cold coffee", "ek peri peri fries") -> intent="add_to_cart", target_item="<item_name>", ui_action="add_to_cart", ui_action_value="<item_name>"
  - "remove the fries" / "ye hata do" -> intent="remove_from_cart", target_item="<item_name>"
  - "checkout" / "pay" / "bill banao" / "done" -> intent="checkout", ui_action="checkout"
- BURGER CUSTOMIZATION & 3D SPLIT:
  - "customize burger" / "split burger" / "burger kholo" -> intent="customize_burger", customization_action="split_burger", ui_action="customize_burger", ui_action_value="split"
  - "swap chicken patty for paneer" / "replace chicken pad with paneer pad" / "chicken patty hata ke paneer lagao" / "paneer patty chahiye" -> intent="customize_burger", customization_action="swap_patty", customization_target="paneer", ui_action="customize_burger", ui_action_value="paneer"
  - "remove onions" / "no onion" / "pyaz mat dalna" -> intent="customize_burger", customization_action="remove_topping", customization_target="onion", ui_action="customize_burger", ui_action_value="remove_onion"
  - "extra cheese" / "cheese slice add karo" -> intent="customize_burger", customization_action="add_topping", customization_target="cheese", ui_action="customize_burger", ui_action_value="add_cheese"
"""

    async def run(
        self,
        user_input: str,
        session: SessionState,
        branch_id: int = 1,
    ) -> AgentResponse:
        system_prompt = self._build_system_prompt(session)

        # Build message history for LangChain
        messages = [SystemMessage(content=system_prompt)]
        for turn in session.conversation_history[-4:]:
            if turn.role == "user":
                messages.append(HumanMessage(content=turn.content))
            elif turn.role == "assistant":
                messages.append(AIMessage(content=turn.content))
        messages.append(HumanMessage(content=user_input))

        decision: CashierDecision | None = None

        # Execute LangChain Structured Chain
        try:
            if hasattr(self.llm, "_llm"):
                structured_chain = self.llm._llm.with_structured_output(CashierDecision)
                decision = await structured_chain.ainvoke(messages)
                logger.info(
                    "langchain_cashier_decision",
                    intent=decision.intent,
                    target=decision.target_item,
                    psychology=decision.psychological_principle_applied,
                )
        except Exception as exc:
            logger.warning("langchain_structured_chain_fallback", error=str(exc))

        # Fallback heuristic if structured output fails
        if not decision:
            decision = self._fallback_decision(user_input, session)

        # Ensure category and dietary preference are accurately extracted from decision and raw input
        raw_text = user_input.lower()
        category = decision.category
        if not category:
            if any(w in raw_text for w in ["burger", "whopper"]):
                category = "burger"
            elif any(w in raw_text for w in ["drink", "coffee", "coke", "thanda", "beverage"]):
                category = "drink"
            elif any(w in raw_text for w in ["fries", "side", "peri peri", "rings", "snack"]):
                category = "side"
            elif any(w in raw_text for w in ["dessert", "sweet", "sundae", "ice cream", "meetha"]):
                category = "dessert"

        pref = decision.preference
        if not pref:
            import re
            if re.search(r"\b(veg|veggie|vegetarian|shakahari|no\s*meat|plant|green\s*(dot|mark)|without\s*meat|no\s*chicken|pure\s*veg|sirf\s*veg)\b", raw_text):
                pref = "veg"
            elif re.search(r"\b(non\s*veg|non-veg|nonveg|meat|chicken|red\s*(dot|mark)|mansahari)\b", raw_text):
                pref = "non_veg"
            elif re.search(r"\b(both|all|sab|dono|reset|clear\s*filter)\b", raw_text):
                pref = "both"

        if pref:
            session.food_preference = pref

        # Map decision to kiosk UI action and screen
        target_screen = session.current_screen.name if session.current_screen else "home"
        ui_action = decision.ui_action
        ui_action_value = decision.ui_action_value or decision.target_item or category

        if decision.intent == "filter_menu" or (pref and decision.intent not in ("add_to_cart", "remove_from_cart", "customize_burger", "checkout")):
            ui_action = f"filter_{pref}"
            ui_action_value = pref
            if category:
                target_screen = f"recommended_{category}s" if category in ("burger", "drink", "side", "dessert") else f"recommended_{category}"
            elif target_screen in ("home", "category_selection"):
                target_screen = "recommended_burgers"

        elif decision.intent == "open_category" or (category and decision.intent not in ("add_to_cart", "remove_from_cart", "customize_burger", "checkout")):
            cat = (category or "burger").lower()
            if pref:
                ui_action = f"filter_{pref}"
                ui_action_value = pref
            else:
                ui_action = "open_category"
                ui_action_value = cat
            target_screen = f"recommended_{cat}s" if cat in ("burger", "drink", "side", "dessert") else f"recommended_{cat}"
            session.last_category = cat

        elif decision.intent == "add_to_cart":
            ui_action = "add_to_cart"
            ui_action_value = decision.target_item or user_input

        elif decision.intent == "recommend":
            ui_action = "get_recommendations"
            cat = category or session.last_category or "burger"
            ui_action_value = cat
            target_screen = f"recommended_{cat}s" if cat in ("burger", "drink", "side", "dessert") else "recommended_burgers"

        elif decision.intent == "checkout":
            ui_action = "checkout"
            target_screen = "cart"

        elif decision.intent == "customize_burger":
            ui_action = "customize_burger"
            target_val = (decision.customization_target or "paneer").lower()
            act = decision.customization_action or "swap_patty"
            ui_action_value = {
                "action": act,
                "target": target_val,
                "remove": "chicken" if any(x in target_val for x in ["paneer", "veg"]) else "patty",
            }

        # Apply sensory polish to spoken message if not already present
        spoken_msg = decision.spoken_message
        if decision.target_item and not any(w in spoken_msg.lower() for w in ["crispy", "flame", "chilled", "warm", "golden"]):
            sensory_cue = self.psychology.get_sensory_cue(decision.target_item)
            spoken_msg = spoken_msg.replace(decision.target_item, sensory_cue)

        return AgentResponse(
            spoken_message=spoken_msg,
            ui_action=ui_action,
            ui_action_value=ui_action_value,
            target_screen=target_screen,
            decision=decision,
        )

    def _fallback_decision(self, user_input: str, session: SessionState) -> CashierDecision:
        import re
        text = user_input.lower()

        # 1. Customization patterns
        if any(w in text for w in ["customize", "split", "patty", "pad", "swap", "paneer", "remove onion"]):
            target = "paneer" if "paneer" in text else "chicken" if "chicken" in text else "veg"
            return CashierDecision(
                intent="customize_burger",
                customization_action="swap_patty" if any(w in text for w in ["swap", "instead", "pad", "patty", "paneer"]) else "split_burger",
                customization_target=target,
                spoken_message=f"Customizing your burger! Slicing out the patty and sliding in our freshly prepared {target.capitalize()} patty for you.",
                psychological_principle_applied="sensory_framing",
                reasoning="Burger customization keyword match in fallback.",
            )

        # 2. Dietary preference patterns (Hinglish, English, indirect dining idioms)
        has_veg = bool(re.search(r"\b(veg|veggie|vegetarian|shakahari|no\s*meat|plant|green\s*(dot|mark)|without\s*meat|no\s*chicken|sirf\s*veg|pure\s*veg)\b", text))
        has_non_veg = bool(re.search(r"\b(non\s*veg|non-veg|nonveg|meat|chicken|red\s*(dot|mark)|mansahari)\b", text))
        has_both = bool(re.search(r"\b(both|all|sab|dono|reset|clear\s*filter)\b", text))
        has_burger = bool(re.search(r"\b(burger|whopper)\b", text))

        if has_both:
            return CashierDecision(
                intent="filter_menu",
                preference="both",
                ui_action="filter_both",
                ui_action_value="both",
                spoken_message="Showing our full menu with both pure veg and flame-grilled non-veg selections.",
                psychological_principle_applied="reciprocal_warmth",
                reasoning="Show both / reset filter keyword match in fallback.",
            )
        elif has_veg:
            if has_burger:
                return CashierDecision(
                    intent="open_category",
                    category="burger",
                    preference="veg",
                    ui_action="filter_veg",
                    ui_action_value="veg",
                    spoken_message="Opening our 100% pure vegetarian flame-grilled burgers for you! What catches your eye?",
                    psychological_principle_applied="sensory_framing",
                    reasoning="Veg burger inquiry match in fallback.",
                )
            return CashierDecision(
                intent="filter_menu",
                preference="veg",
                ui_action="filter_veg",
                ui_action_value="veg",
                spoken_message="Filtering our 100% pure vegetarian menu for you! Everything is prepared with fresh greens and crispy plant-based goodness.",
                psychological_principle_applied="reciprocal_warmth",
                reasoning="Vegetarian preference match in fallback.",
            )
        elif has_non_veg:
            if has_burger:
                return CashierDecision(
                    intent="open_category",
                    category="burger",
                    preference="non_veg",
                    ui_action="filter_non_veg",
                    ui_action_value="non_veg",
                    spoken_message="Showing our succulent, flame-grilled chicken burgers for you! Which one would you like to try?",
                    psychological_principle_applied="sensory_framing",
                    reasoning="Non-veg burger inquiry match in fallback.",
                )
            return CashierDecision(
                intent="filter_menu",
                preference="non_veg",
                ui_action="filter_non_veg",
                ui_action_value="non_veg",
                spoken_message="Showing our succulent, flame-grilled chicken and non-veg favorites for you!",
                psychological_principle_applied="sensory_framing",
                reasoning="Non-vegetarian preference match in fallback.",
            )
        elif has_burger:
            return CashierDecision(
                intent="open_category",
                category="burger",
                spoken_message="Opening our flame-grilled burgers for you! What catches your eye?",
                psychological_principle_applied="sensory_framing",
                reasoning="Burger keyword match in fallback.",
            )
        elif re.search(r"\b(drink|coffee|coke|thanda|beverage|thirst|thirsty|peene|shake|frappe)\b", text):
            return CashierDecision(
                intent="open_category",
                category="drink",
                spoken_message="Here are our chilled beverages and rich Cold Coffees! Which one would you like?",
                psychological_principle_applied="sensory_framing",
                reasoning="Drink/thirst keyword match in fallback.",
            )
        elif re.search(r"\b(fries|side|peri peri|rings|snack|munch|crunch)\b", text):
            return CashierDecision(
                intent="open_category",
                category="side",
                spoken_message="Sure! Showing our hot, golden-crispy fries and crunchy sides.",
                psychological_principle_applied="sensory_framing",
                reasoning="Side/snack keyword match in fallback.",
            )
        elif re.search(r"\b(dessert|sweet|sundae|ice cream|meetha)\b", text):
            return CashierDecision(
                intent="open_category",
                category="dessert",
                spoken_message="Here are our velvety soft-serves and warm chocolate sundaes!",
                psychological_principle_applied="sensory_framing",
                reasoning="Dessert/sweet keyword match in fallback.",
            )
        elif re.search(r"\b(recommend|special|best seller|popular|accha|kya lu|kya khau)\b", text):
            return CashierDecision(
                intent="recommend",
                spoken_message="I highly recommend our signature flame-grilled Whopper or crispy Peri Peri Fries! Would you like to check them out?",
                psychological_principle_applied="hicks_binary_choice",
                reasoning="Recommendation keyword match in fallback.",
            )
        elif any(w in text for w in ["pay", "checkout", "bill", "done"]):
            return CashierDecision(
                intent="checkout",
                spoken_message="Taking you to review and pay for your delicious order!",
                psychological_principle_applied="reciprocal_warmth",
                reasoning="Checkout keyword match in fallback.",
            )
        return CashierDecision(
            intent="chit_chat",
            spoken_message="I'm here to help you order! Would you like to explore our flame-grilled burgers or chilled beverages today?",
            psychological_principle_applied="hicks_binary_choice",
            reasoning="General welcome in fallback.",
        )
