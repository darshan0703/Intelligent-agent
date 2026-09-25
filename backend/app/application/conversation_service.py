"""
app/application/conversation_service.py
Core end-to-end conversation orchestration pipeline.
Two-tier routing: Screen Intent -> Cashier Agent with structured fallback.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from app.application.cart_service import CartService
from app.application.session_service import SessionService
from app.domain.session.entities import ConversationTurn
from app.intelligence.agent.cashier_agent import CashierAgent
from app.intelligence.entity_resolution.resolver import EntityResolver
from app.intelligence.intent.screen_intent import extract_screen_intent
from app.observability.logging import get_logger
from app.ports.catalog_port import CatalogRepository
from app.ports.llm_port import LanguageModelPort
from app.prompts.registry import get_prompt_registry

logger = get_logger(__name__)


@dataclass
class ConversationResponse:
    message: str
    screen: str | None
    ui_action: str | None
    ui_action_value: str | None
    cart_summary: dict | None
    data: dict | None = None


class ConversationService:
    def __init__(
        self,
        session_service: SessionService,
        cart_service: CartService,
        catalog: CatalogRepository,
        llm: LanguageModelPort,
        agent: CashierAgent,
    ):
        self.session_service = session_service
        self.cart_service = cart_service
        self.catalog = catalog
        self.llm = llm
        self.agent = agent
        self.resolver = EntityResolver()
        self.prompts = get_prompt_registry()

    def _serialize_item(self, item) -> dict:
        is_veg = False
        if item.food_type:
            ft = str(item.food_type.value if hasattr(item.food_type, "value") else item.food_type).lower()
            is_veg = "veg" in ft and "non" not in ft

        img = item.image or ""
        if img and not img.startswith("http") and not img.startswith("/"):
            img = "/" + img
        meal_img = item.meal_image or img
        if meal_img and not meal_img.startswith("http") and not meal_img.startswith("/"):
            meal_img = "/" + meal_img

        return {
            "id": item.id,
            "name": item.name,
            "price": float(item.price.amount),
            "foodType": "veg" if is_veg else "non veg",
            "type": "veg" if is_veg else "non veg",
            "category": str(item.category.value if hasattr(item.category, "value") else item.category),
            "image": img or "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500&auto=format&fit=crop&q=60",
            "meal_image": meal_img or img,
            "shortDescription": item.short_description or item.name,
            "longDescription": item.long_description or item.name,
            "is_meal_available": item.is_meal_available,
            "stock": item.inventory.stock if item.inventory else 50,
        }

    async def _build_screen_data(self, category: str, branch_id: int = 1, session_id: str = "default-kiosk-session") -> dict:
        items = await self.catalog.get_by_category(category, branch_id)
        if not items:
            items = await self.catalog.get_all_available(branch_id)

        from app.intelligence.recommendation.llm_merchandising_engine import (
            get_impression_penalty,
            record_impressions,
        )

        serialized = [self._serialize_item(i) for i in items]
        for item in serialized:
            penalty = get_impression_penalty(session_id, item["id"])
            item["score"] = penalty * (1.25 if "whopper" in item["name"].lower() or "fries" in item["name"].lower() else 1.0)
            item["badge"] = "🔥 Popular Choice"
            item["synergy_reason"] = "Customer favorite at Burger King"

        serialized.sort(key=lambda x: x.get("score", 1.0), reverse=True)
        record_impressions(session_id, [x["id"] for x in serialized[:8]])

        veg_items = [i for i in serialized if i.get("foodType") == "veg" or i.get("type") == "veg"]
        non_veg_items = [i for i in serialized if i.get("foodType") != "veg" and i.get("type") != "veg"]

        def build_set(lst, fallback_to_all=False):
            pool = lst if lst else (serialized if fallback_to_all else [])
            if not pool:
                pool = serialized
            prio = pool[:2] if len(pool) >= 2 else (pool * 2)[:2]
            remaining = [i for i in pool if i["id"] not in {p["id"] for p in prio}]
            if not remaining:
                remaining = pool
            prem = sorted(remaining, key=lambda x: x["price"], reverse=True)[:2]
            if len(prem) < 2:
                candidates = [i for i in pool if i["id"] not in {p["id"] for p in prem}]
                prem = (prem + (candidates if candidates else pool))[:2]
            used_ids = {p["id"] for p in prio} | {p["id"] for p in prem}
            add = [i for i in pool if i["id"] not in used_ids][:4]
            if len(add) < 4:
                extra = [i for i in pool if i["id"] not in {a["id"] for a in add}]
                add = (add + (extra if extra else pool) + pool)[:4]
            return {
                "priority": prio,
                "premium": prem,
                "additional": add,
            }

        both_priority = []
        if veg_items:
            both_priority.append(veg_items[0])
        if non_veg_items:
            both_priority.append(non_veg_items[0])
        if len(both_priority) < 2:
            both_priority = serialized[:2]

        both_premium = sorted(serialized, key=lambda x: x["price"], reverse=True)[:2]
        both_additional = [i for i in serialized if i not in both_priority and i not in both_premium][:4]

        by_price = sorted(serialized, key=lambda x: x["price"], reverse=True)
        return {
            "category": category,
            "both": {
                "priority": both_priority,
                "premium": both_premium,
                "additional": both_additional,
            },
            "veg": build_set(veg_items, fallback_to_all=False) if veg_items else build_set(serialized, fallback_to_all=True),
            "non_veg": build_set(non_veg_items, fallback_to_all=False) if non_veg_items else build_set(serialized, fallback_to_all=True),
            "priority": serialized[:2],
            "premium": by_price[:2],
            "additional": serialized[2:6],
        }


    async def _match_item_from_text(self, text: str, branch_id: int = 1):
        import re
        t = text.strip().lower()

        num_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
            "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
        }

        add_patterns = [
            r"^(?:please\s+)?(?:add|order|give\s+me|i\s+want\s+to\s+order|i\s+want\s+to\s+have|i\s+want\s+to\s+eat|i\s+want|i'll\s+take|get\s+me|i\s+need|can\s+i\s+have|can\s+i\s+get|can\s+you\s+add|can\s+we\s+get|put|daal\s+do)\s+(?:a\s+|an\s+|the\s+)?(?:(\w+)\s+)?(.+)$",
            r"^(?:mujhe\s+|hume\s+|bhai\s+)?(?:(\w+)\s+)?(.+?)\s+(?:add\s*karo|daal\s*do|dedo|de\s*do|chahiye|laga\s*do|bhejo)$",
            r"^(?:(\w+)\s+)?(crispy\s+veg|crispy\s+chicken|whopper|whoppers|veg\s+whopper|chicken\s+whopper|paneer\s+whopper|paneer\s+royale|peri\s+peri\s+fries|fries|coke|coca\s+cola|cold\s+coffee|chocolate\s+sundae|vanilla\s+softie|nuggets)(?:\s+burger|\s+burgers|\s+dena|\s+please)?$",
        ]

        raw_query = ""
        qty = 1

        for pat in add_patterns:
            m = re.match(pat, t)
            if m:
                groups = m.groups()
                if len(groups) == 2:
                    qty_cand, q_cand = groups
                    if qty_cand and qty_cand.lower() in num_map:
                        qty = num_map[qty_cand.lower()]
                    else:
                        q_cand = f"{qty_cand} {q_cand}" if qty_cand else q_cand
                    raw_query = q_cand.strip() if q_cand else ""
                elif len(groups) == 1:
                    raw_query = groups[0].strip()
                break

        if not raw_query:
            if t.startswith("add ") or t.startswith("order "):
                raw_query = re.sub(r"^(?:add|order)\s+(?:a\s+|an\s+|the\s+)?", "", t).strip()

        if not raw_query:
            return None, 1

        clean_q = re.sub(r"\b(burger|burgers|drink|drinks|please|to\s+(?:my\s+|the\s+)?cart|in\s+(?:my\s+|the\s+)?cart|bhai|dena|karo|mujhe|chahiye)\b", "", raw_query).strip()
        if clean_q.endswith("s") and not clean_q.endswith("fries") and not clean_q.endswith("wings") and not clean_q.endswith("nuggets"):
            clean_q_stemmed = clean_q[:-1].strip()
        else:
            clean_q_stemmed = clean_q

        all_items = await self.catalog.get_all_available(branch_id)
        if not all_items:
            return None, 1

        aliases = {
            "coke": "Large Coca cola",
            "coca cola": "Large Coca cola",
            "fries": "Fries (Medium)",
            "french fries": "Fries (Medium)",
            "peri peri fries": "Peri Peri Fries (Medium)",
            "cold coffee": "Classic Cold Coffee",
            "coffee": "Classic Cold Coffee",
            "whopper": "Veg Whopper",
            "veg burger": "Crispy Veg",
            "chicken burger": "Crispy Chicken",
            "paneer burger": "Paneer Royale",
            "sundae": "Chocolate Sundae",
            "ice cream": "Vanilla Softie",
            "nuggets": "Crunchy Chicken Nuggets (4 Pc)",
        }
        for alias, target_name in aliases.items():
            if alias == clean_q or alias == clean_q_stemmed:
                target_item = next((i for i in all_items if i.name.lower() == target_name.lower()), None)
                if target_item:
                    return target_item, qty

        best_item = None
        best_score = 0.0

        for item in all_items:
            item_name_lower = item.name.lower()
            if clean_q_stemmed == item_name_lower or clean_q == item_name_lower:
                return item, qty
            if clean_q_stemmed in item_name_lower or clean_q in item_name_lower:
                score = len(clean_q_stemmed) / len(item_name_lower) + 0.5
                if score > best_score:
                    best_score = score
                    best_item = item
            elif item_name_lower in clean_q or item_name_lower in clean_q_stemmed:
                score = len(item_name_lower) / len(clean_q) + 0.4
                if score > best_score:
                    best_score = score
                    best_item = item

            q_tokens = set(clean_q.split())
            name_tokens = set(item_name_lower.replace("(", "").replace(")", "").split())
            if q_tokens and name_tokens:
                overlap = len(q_tokens & name_tokens)
                if overlap > 0:
                    token_score = overlap / max(len(q_tokens), len(name_tokens))
                    if token_score > best_score:
                        best_score = token_score
                        best_item = item

        for alias, target_name in aliases.items():
            if alias in clean_q or clean_q in alias:
                target_item = next((i for i in all_items if i.name.lower() == target_name.lower()), None)
                if target_item:
                    return target_item, qty

        if best_item and best_score >= 0.4:
            return best_item, qty
        return None, 1

    async def _try_fast_path(self, text: str, session: SessionState, branch_id: int) -> ConversationResponse | None:
        import re
        t = text.strip().lower()

        # 1. Back navigation (0ms)
        if re.search(r"^(go\s+)?back$|^previous(\s+screen)?$|^piche\s*jao$|^wapas\s*jao$", t):
            msg = "Going back to the previous screen."
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen="home",
                ui_action="go_back",
                ui_action_value="back",
                cart_summary=None,
            )

        # 2. Dietary Filter fast-path (0ms)
        if re.search(r"^(show\s+)?(veg|veggie|vegetarian)(\s+only)?$|^shakahari$|^sirf\s*veg$|^kuch\s*veg(\s*dikhana)?$", t):
            session.food_preference = "veg"
            target_scr = session.current_screen.name if session.current_screen else "recommended_burgers"
            if target_scr in ("home", "category_selection"):
                target_scr = "recommended_burgers"
            cat_slug = target_scr.replace("recommended_", "").rstrip("s")
            cat_slug = "burger" if "burger" in cat_slug else ("drink" if "drink" in cat_slug else ("side" if "side" in cat_slug else ("dessert" if "dessert" in cat_slug else "burger")))
            screen_data = await self._build_screen_data(cat_slug, branch_id, session_id=session.session_id)
            if screen_data:
                screen_data["preference"] = "veg"
            msg = "Showing our delicious 100% pure vegetarian options!"
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen=target_scr,
                ui_action="filter_veg",
                ui_action_value="veg",
                cart_summary=None,
                data=screen_data,
            )

        if re.search(r"^(show\s+)?non\s*veg(\s+only)?$|^mansahari$|^sirf\s*non\s*veg$", t):
            session.food_preference = "non_veg"
            target_scr = session.current_screen.name if session.current_screen else "recommended_burgers"
            if target_scr in ("home", "category_selection"):
                target_scr = "recommended_burgers"
            cat_slug = target_scr.replace("recommended_", "").rstrip("s")
            cat_slug = "burger" if "burger" in cat_slug else ("drink" if "drink" in cat_slug else ("side" if "side" in cat_slug else ("dessert" if "dessert" in cat_slug else "burger")))
            screen_data = await self._build_screen_data(cat_slug, branch_id, session_id=session.session_id)
            if screen_data:
                screen_data["preference"] = "non_veg"
            msg = "Showing our mouth-watering non-veg selections!"
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen=target_scr,
                ui_action="filter_non_veg",
                ui_action_value="non_veg",
                cart_summary=None,
                data=screen_data,
            )

        if re.search(r"^(show\s+)?(both|all)(\s+items)?$|^reset\s+filter$|^sab\s*dikhana$", t):
            session.food_preference = "both"
            target_scr = session.current_screen.name if session.current_screen else "recommended_burgers"
            cat_slug = target_scr.replace("recommended_", "").rstrip("s")
            cat_slug = "burger" if "burger" in cat_slug else ("drink" if "drink" in cat_slug else ("side" if "side" in cat_slug else ("dessert" if "dessert" in cat_slug else "burger")))
            screen_data = await self._build_screen_data(cat_slug, branch_id, session_id=session.session_id)
            if screen_data:
                screen_data["preference"] = "both"
            msg = "Showing all items on the menu."
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen=target_scr,
                ui_action="filter_both",
                ui_action_value="both",
                cart_summary=None,
                data=screen_data,
            )

        # 3. Direct Category fast-path (0ms)
        cat_map = {
            "burger": ["burger", "burgers", "show burgers", "open burgers", "burger menu", "burger chahiye"],
            "drink": ["drink", "drinks", "beverage", "beverages", "show drinks", "open drinks", "shakes", "cold drinks"],
            "side": ["side", "sides", "fries", "show sides", "open sides", "french fries", "snacks"],
            "dessert": ["dessert", "desserts", "sweet", "sweets", "sundae", "ice cream", "show desserts", "open desserts"],
        }
        for cat, phrases in cat_map.items():
            if t in phrases or t == f"i want {cat}" or t == f"show me {cat}" or t == f"i want a {cat}":
                session.last_category = cat
                target_scr = f"recommended_{cat}s"
                screen_data = await self._build_screen_data(cat, branch_id)
                msg = f"Opening our delicious {cat} selections for you!"
                session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
                await self.session_service.repo.update(session)
                return ConversationResponse(
                    message=msg,
                    screen=target_scr,
                    ui_action="open_category",
                    ui_action_value=cat,
                    cart_summary=None,
                    data=screen_data,
                )

        # 4. Direct Checkout / Cart fast-path (0ms)
        if re.search(r"^(go\s+to\s+)?(checkout|cart|view\s+cart|open\s+cart|pay|review\s+and\s+pay|bill\s+banao)$", t):
            msg = "Taking you straight to review and checkout your order!"
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            return ConversationResponse(
                message=msg,
                screen="cart",
                ui_action="checkout",
                ui_action_value="checkout",
                cart_summary=None,
            )

        # 5. Direct Item Add-to-Cart Fast-Path (0ms speech-to-cart addition)
        matched_item, qty = await self._match_item_from_text(t, branch_id)
        if matched_item:
            await self.cart_service.add_item(session.session_id, matched_item.id, quantity=qty, branch_id=branch_id)
            cart = await self.cart_service.get_cart(session.session_id)
            
            item_desc = f"{qty} {matched_item.name}" if qty > 1 else matched_item.name
            cat_str = str(matched_item.category.value if hasattr(matched_item.category, "value") else matched_item.category).lower()
            
            if "burger" in cat_str:
                msg = f"I've added {item_desc} to your cart! Your subtotal is Rs.{cart.subtotal.amount:.0f}. Would you like to add an ice-cold beverage or crispy fries with that?"
            elif "side" in cat_str:
                msg = f"Added {item_desc} to your cart! Your subtotal is Rs.{cart.subtotal.amount:.0f}. How about an ice-cold beverage to pair with it?"
            elif "drink" in cat_str:
                msg = f"Added {item_desc} to your cart! Your subtotal is Rs.{cart.subtotal.amount:.0f}."
            else:
                msg = f"Added {item_desc} to your cart! Your subtotal is Rs.{cart.subtotal.amount:.0f}."
                
            session.add_turn(ConversationTurn(role="assistant", content=msg, timestamp=datetime.utcnow(), metadata={}))
            await self.session_service.repo.update(session)
            
            return ConversationResponse(
                message=msg,
                screen=session.current_screen.name if session.current_screen else "home",
                ui_action="item_added",
                ui_action_value=str(matched_item.id),
                cart_summary={
                    "item_count": cart.item_count,
                    "subtotal": str(cart.subtotal.amount),
                },
            )

        return None

    async def process_message(
        self,
        session_id: str,
        user_input: str,
        branch_id: int = 1,
    ) -> ConversationResponse:
        session = await self.session_service.get_session(session_id)
        if not session:
            session = await self.session_service.start_session(session_id=session_id)
            session_id = session.session_id

        session.add_turn(ConversationTurn(role="user", content=user_input, timestamp=datetime.utcnow(), metadata={}))

        # Tier 0: 0ms High-Confidence Fast-Path Heuristics for direct kiosk controls
        fast_res = await self._try_fast_path(user_input, session, branch_id)
        if fast_res:
            return fast_res

        # Tier 1: Cashier Agent (single high-performance structured call)
        agent_res = await self.agent.run(user_input=user_input, session=session, branch_id=branch_id)
        session.add_turn(ConversationTurn(role="assistant", content=agent_res.spoken_message, timestamp=datetime.utcnow(), metadata={}))
        await self.session_service.repo.update(session)

        # Synchronize voice action directly to domain cart
        if agent_res.ui_action in ("add_to_cart", "add_item") and agent_res.ui_action_value:
            try:
                matches = await self.catalog.search_by_name(agent_res.ui_action_value, branch_id)
                if matches:
                    qty = 1
                    if agent_res.decision and hasattr(agent_res.decision, "quantity") and agent_res.decision.quantity:
                        qty = agent_res.decision.quantity
                    await self.cart_service.add_item(session_id, matches[0].id, quantity=qty, branch_id=branch_id)
            except Exception as exc:
                logger.warning("failed_to_add_cart_item_from_voice", error=str(exc))

        cart = await self.cart_service.get_cart(session_id)
        cart_data = {
            "item_count": cart.item_count,
            "subtotal": str(cart.subtotal.amount),
        }

        # Build screen recommendation data if navigating to category
        target_scr = agent_res.target_screen or (session.current_screen.name if session.current_screen else "home")
        screen_data = None
        if "burger" in target_scr:
            screen_data = await self._build_screen_data("burger", branch_id, session_id=session_id)
        elif "drink" in target_scr:
            screen_data = await self._build_screen_data("drink", branch_id, session_id=session_id)
        elif "side" in target_scr:
            screen_data = await self._build_screen_data("side", branch_id, session_id=session_id)
        elif "dessert" in target_scr:
            screen_data = await self._build_screen_data("dessert", branch_id, session_id=session_id)

        if screen_data and session.food_preference:
            screen_data["preference"] = session.food_preference

        return ConversationResponse(
            message=agent_res.spoken_message,
            screen=target_scr,
            ui_action=agent_res.ui_action,
            ui_action_value=agent_res.ui_action_value,
            cart_summary=cart_data,
            data=screen_data,
        )
