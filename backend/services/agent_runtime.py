import concurrent.futures
import json
import os

from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from perf import get_current_tracer
from debugging.context_capture import capture_llm_call

CONCURRENCY_SAFE_READ_TOOLS = frozenset({"get_menu_item_details", "get_recommendations"})


def is_concurrency_safe_tool(tool_obj, name: str) -> bool:
    """
    Verify whether a tool is strictly read-only and safe for concurrent execution.
    Reclassifies any unsafe or stateful tool (e.g. select_product, open_category, screen_action)
    as serial/resolution rather than relying solely on name strings.
    """
    STATEFUL_TOOLS = {"select_product", "open_category", "screen_action"}
    if name in STATEFUL_TOOLS:
        return False

    if tool_obj is not None:
        meta = getattr(tool_obj, "metadata", None)
        if isinstance(meta, dict):
            if meta.get("read_only") is False or meta.get("concurrency_safe") is False:
                return False
            if meta.get("read_only") and meta.get("concurrency_safe"):
                return True
        if getattr(tool_obj, "read_only", None) is False:
            return False
        if getattr(tool_obj, "concurrency_safe", None) is False:
            return False
        if getattr(tool_obj, "read_only", False) and getattr(tool_obj, "concurrency_safe", False):
            return True

    return name in CONCURRENCY_SAFE_READ_TOOLS


def _format_cart_followup(conversation_context: dict) -> str:
    unfulfilled = [
        p for p in conversation_context.get("pending_items", [])
        if isinstance(p, dict) and not p.get("fulfilled") and p.get("quantity", 1) > p.get("fulfilled_quantity", 0)
    ]
    if unfulfilled:
        unresolved_parts = [
            f"{p.get('quantity', 1) - p.get('fulfilled_quantity', 0)} {p.get('name')}"
            for p in unfulfilled
        ]
        return f"You also requested {', '.join(unresolved_parts)}—shall we get that ready next?"
    return "Would you like to keep shopping or head to checkout?"



class AgentRuntime:
    """
    Provider-independent orchestration layer for TheAtom's cashier agent.
    """

    def __init__(
        self,
        model,
        tools_factory,
        system_prompt,
    ):
        self.model = model
        self.tools_factory = tools_factory
        self.system_prompt = system_prompt

    def run(
        self,
        user_input,
        conversation_context,
        customer_context,
        history,
        customer_context_builder=None,
    ):
        if isinstance(conversation_context, dict):
            conversation_context["current_user_message"] = user_input

        tools = self.tools_factory(
            conversation_context
        )

        llm_with_tools = self.model.bind_tools(
            tools
        )

        tool_map = {
            tool.name: tool
            for tool in tools
        }

        messages = [
            SystemMessage(
                content=f"""{self.system_prompt}

CURRENT CUSTOMER CONTEXT:

{customer_context}
"""
            ),
        ]

        messages.extend(history)

        messages.append(
            HumanMessage(
                content=user_input
            )
        )

        turn_number = sum(1 for m in history if isinstance(m, HumanMessage)) + 1
        session_id = conversation_context.get("session_id") if isinstance(conversation_context, dict) else None
        model_name = getattr(self.model, "model_name", None)
        if not isinstance(model_name, str):
            model_name = getattr(getattr(self.model, "primary_model", None), "model_name", None)
        if not isinstance(model_name, str):
            model_name = "openai/gpt-oss-20b"

        tracer = get_current_tracer()
        interaction_id = getattr(tracer, "interaction_id", None) if tracer else None

        with capture_llm_call(
            messages=messages,
            tools=tools,
            interaction_id=interaction_id,
            session_id=session_id,
            turn_number=turn_number,
            invocation_index=1,
            invocation_type="tool_selection",
            model_name=model_name,
            system_prompt=self.system_prompt,
            customer_context=customer_context,
            current_user_input=user_input,
        ) as cap:
            if tracer:
                with tracer.measure("llm_call_1"):
                    response = llm_with_tools.invoke(messages)
            else:
                response = llm_with_tools.invoke(messages)
            cap.record_response(response)

        messages.append(response)

        llm_call_count = 1
        while response.tool_calls:

            print("\nAGENT TOOL CALLS:")
            print(response.tool_calls)

            # 1. Deduplicate tool calls with identical (name, args) within this turn
            unique_calls = []
            call_id_to_canonical_id = {}
            seen_signatures = {}

            for tool_call in response.tool_calls:
                t_name = tool_call["name"]
                t_args = tool_call.get("args") or {}
                t_id = tool_call["id"]
                try:
                    sig = (t_name, json.dumps(t_args, sort_keys=True))
                except Exception:
                    sig = (t_name, str(sorted(t_args.items())))

                if sig in seen_signatures:
                    call_id_to_canonical_id[t_id] = seen_signatures[sig]
                else:
                    seen_signatures[sig] = t_id
                    call_id_to_canonical_id[t_id] = t_id
                    unique_calls.append(tool_call)

            has_upgrade_to_meal = any(
                tc.get("name") == "screen_action" and (tc.get("args") or {}).get("control") == "upgrade_to_meal"
                for tc in unique_calls
            )
            if isinstance(conversation_context, dict):
                if has_upgrade_to_meal:
                    conversation_context["_has_upgrade_to_meal_in_turn"] = True
                else:
                    conversation_context.pop("_has_upgrade_to_meal_in_turn", None)

            # 2. Dependency ordering:
            # Stage 1: Independent read-only tools and product resolution tools
            # Stage 2: Dependent screen actions and navigation
            stage1_calls = []
            stage2_calls = []

            for tc in unique_calls:
                if tc["name"] in ["get_menu_item_details", "get_recommendations", "select_product"]:
                    stage1_calls.append(tc)
                else:
                    stage2_calls.append(tc)

            results_by_id = {}
            executed_results = []

            # Pure read-only lookups run concurrently if more than one
            readonly_calls = []
            resolution_calls = []
            for tc in stage1_calls:
                t_name = tc["name"]
                t_obj = tool_map.get(t_name)
                if is_concurrency_safe_tool(t_obj, t_name):
                    readonly_calls.append(tc)
                else:
                    resolution_calls.append(tc)

            if len(readonly_calls) > 1:
                def _run_readonly(tc):
                    name = tc["name"]
                    args = tc.get("args") or {}
                    selected = tool_map.get(name)
                    if not selected:
                        return tc["id"], name, args, {"error": f"Tool '{name}' not found."}
                    try:
                        if tracer:
                            with tracer.measure("tool_execution", tool=name):
                                res = selected.invoke(args)
                        else:
                            res = selected.invoke(args)
                        return tc["id"], name, args, res
                    except Exception as exc:
                        return tc["id"], name, args, {"error": str(exc)}

                max_workers = min(4, len(readonly_calls))
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(_run_readonly, tc) for tc in readonly_calls]
                    for f in concurrent.futures.as_completed(futures):
                        tc_id, name, args, res = f.result()
                        results_by_id[tc_id] = res
                        executed_results.append((name, args, res))
            elif len(readonly_calls) == 1:
                tc = readonly_calls[0]
                name = tc["name"]
                args = tc.get("args") or {}
                selected = tool_map.get(name)
                if not selected:
                    res = {"error": f"Tool '{name}' not found."}
                else:
                    try:
                        if tracer:
                            with tracer.measure("tool_execution", tool=name):
                                res = selected.invoke(args)
                        else:
                            res = selected.invoke(args)
                    except Exception as exc:
                        res = {"error": str(exc)}
                results_by_id[tc["id"]] = res
                executed_results.append((name, args, res))

            # Execute product resolutions (e.g. select_product)
            for tc in resolution_calls:
                name = tc["name"]
                args = tc.get("args") or {}
                selected = tool_map.get(name)
                if not selected:
                    res = {"error": f"Tool '{name}' not found."}
                else:
                    try:
                        if tracer:
                            with tracer.measure("tool_execution", tool=name):
                                res = selected.invoke(args)
                        else:
                            res = selected.invoke(args)
                    except Exception as exc:
                        res = {"error": str(exc)}
                results_by_id[tc["id"]] = res
                executed_results.append((name, args, res))

            # Determine product resolution outcomes
            has_failed_product_resolution = any(
                r[0] == "select_product" and (
                    not isinstance(r[2], dict) or not r[2].get("success") or r[2].get("status") == "not_found"
                )
                for r in executed_results
            )

            has_successful_select_product = any(
                r[0] == "select_product" and isinstance(r[2], dict) and r[2].get("success")
                for r in executed_results
            )

            # Stage 2: Dependent screen actions
            for tc in stage2_calls:
                name = tc["name"]
                args = tc.get("args") or {}
                tc_id = tc["id"]
                selected = tool_map.get(name)

                if not selected:
                    res = {"error": f"Tool '{name}' not found."}
                elif has_failed_product_resolution and name == "screen_action" and args.get("control") in ["add_to_cart", "select_meal", "upgrade_to_meal"]:
                    res = {
                        "success": False,
                        "error": "Cannot execute screen action because product resolution failed.",
                    }
                elif (
                    name == "screen_action"
                    and args.get("control") == "add_to_cart"
                    and has_successful_select_product
                    and not conversation_context.get("explicit_meal_intent")
                ):
                    res = {
                        "success": False,
                        "error": (
                            "Cannot add to cart in the same turn as selecting a product. "
                            "Keep cart unchanged and ask: 'Would you like to make that a meal?'"
                        ),
                        "pending_meal_offer": True,
                    }
                else:
                    try:
                        if tracer:
                            with tracer.measure("tool_execution", tool=name):
                                res = selected.invoke(args)
                        else:
                            res = selected.invoke(args)
                    except Exception as exc:
                        res = {"error": str(exc)}

                results_by_id[tc_id] = res
                executed_results.append((name, args, res))

            # Record ToolMessage in exact order of original tool_calls
            for tc in response.tool_calls:
                t_id = tc["id"]
                canonical_id = call_id_to_canonical_id.get(t_id, t_id)
                tool_res = results_by_id.get(canonical_id, {"error": "Execution missing."})
                messages.append(
                    ToolMessage(
                        content=str(tool_res),
                        tool_call_id=t_id,
                    )
                )

            # Fast-path confirmation: check if tool execution performed a deterministic action
            # that can be confirmed immediately without an unnecessary second LLM call.
            deterministic_confirmation = self._get_deterministic_confirmation(
                executed_results,
                conversation_context,
            )
            if deterministic_confirmation is not None:
                if tracer:
                    tracer.log(
                        "deterministic_confirmation_applied",
                        control=executed_results[0][1].get("control"),
                    )
                response = AIMessage(content=deterministic_confirmation)
                messages.append(response)
                break

            if customer_context_builder:
                try:
                    updated_context = customer_context_builder(conversation_context)
                    if updated_context and len(messages) > 0 and isinstance(messages[0], SystemMessage):
                        customer_context = updated_context
                        messages[0] = SystemMessage(
                            content=f"""{self.system_prompt}

CURRENT CUSTOMER CONTEXT:

{updated_context}
"""
                        )
                except Exception as ctx_err:
                    print(f"Error updating customer context in runtime: {ctx_err}")

            llm_call_count += 1
            with capture_llm_call(
                messages=messages,
                tools=tools,
                interaction_id=interaction_id,
                session_id=session_id,
                turn_number=turn_number,
                invocation_index=llm_call_count,
                invocation_type="followup_after_tool",
                model_name=model_name,
                system_prompt=self.system_prompt,
                customer_context=customer_context,
                current_user_input=user_input,
            ) as cap:
                if tracer:
                    with tracer.measure(f"llm_call_{llm_call_count}"):
                        response = llm_with_tools.invoke(messages)
                else:
                    response = llm_with_tools.invoke(messages)
                cap.record_response(response)

            messages.append(response)

        conversation_messages = []

        for message in messages:

            if isinstance(
                message,
                (
                    HumanMessage,
                    AIMessage,
                    ToolMessage,
                ),
            ):
                conversation_messages.append(
                    message
                )

        conversation_context[
            "conversation_history"
        ] = conversation_messages

        return response.content

    def _get_deterministic_confirmation(
        self,
        executed_results,
        conversation_context,
    ):
        """
        Produce a direct, natural confirmation for deterministic actions (e.g. add_to_cart)
        without executing a redundant second LLM call.
        Returns the confirmation text if eligible, or None if the flow requires full LLM reasoning.
        """
        for t_name, t_args, t_res in executed_results:
            if t_name == "select_product" and isinstance(t_res, dict) and t_res.get("success"):
                meal_offer = t_res.get("meal_offer")
                if meal_offer and meal_offer.get("eligible"):
                    return meal_offer.get("suggested_cashier_prompt") or "Would you like to make that a meal?"

        if len(executed_results) != 1:
            return None

        tool_name, tool_args, tool_result = executed_results[0]

        if tool_name != "screen_action":
            return None

        if not isinstance(tool_result, dict) or not tool_result.get("success"):
            return None

        control = tool_args.get("control") or tool_result.get("control")
        if control not in ["add_to_cart", "set_quantity", "increase_quantity", "decrease_quantity", "decline_meal", "swap_meal_item"]:
            return None

        if control == "swap_meal_item":
            if tool_result.get("role") == "drink":
                orig_qty = conversation_context.get("original_requested_quantity", 1)
                if orig_qty > 1:
                    num_words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
                    orig_word = num_words.get(orig_qty, str(orig_qty))
                    rem_word = num_words.get(orig_qty - 1, str(orig_qty - 1))
                    return f"Would you like all {orig_word} burgers as meals, or one meal and the other {rem_word} burgers on their own?"
            return None

        current_screen = conversation_context.get("current_screen")

        if control == "decline_meal" and current_screen == "product":
            orig_qty = conversation_context.get("original_requested_quantity", 1)
            num_words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
            qty_word = num_words.get(orig_qty, str(orig_qty))
            prod_name = conversation_context.get("selected_product", "burger")
            if orig_qty > 1:
                return f"No problem. Shall I add the {qty_word} burgers to your cart?"
            else:
                return f"No problem. Shall I add the {prod_name} to your cart?"

        if control == "set_quantity":
            qty = tool_result.get("quantity", 1)
            if tool_result.get("capped"):
                stock = tool_result.get("available_stock", qty)
                return f"We only have {stock} in stock, so I've set the quantity to {qty}."
            return f"I've updated the quantity to {qty}."

        if control == "increase_quantity" and current_screen == "product":
            qty = tool_result.get("quantity", 1)
            if tool_result.get("capped"):
                stock = tool_result.get("available_stock", qty)
                return f"We only have {stock} in stock, so the quantity is at the maximum of {qty}."
            return f"I've increased the quantity to {qty}."

        if control == "decrease_quantity" and current_screen == "product":
            qty = tool_result.get("quantity", 1)
            return f"I've decreased the quantity to {qty}."

        if control != "add_to_cart":
            return None

        is_meal = tool_result.get("is_meal") or current_screen == "meal_conversion"

        if is_meal:
            active_meal = conversation_context.get("active_meal") or {}
            burger_info = active_meal.get("burger", {})
            b_name = (
                tool_result.get("item")
                or (burger_info.get("name") if isinstance(burger_info, dict) else str(burger_info or ""))
            )
            size = tool_result.get("size") or active_meal.get("size") or "Medium"
            sel_side = active_meal.get("selected_side")
            side_name = (
                tool_result.get("side")
                or (sel_side.get("name") if isinstance(sel_side, dict) else (sel_side if sel_side else None))
            )
            sel_drink = active_meal.get("selected_drink")
            drink_name = (
                tool_result.get("drink")
                or (sel_drink.get("name") if isinstance(sel_drink, dict) else (sel_drink if sel_drink else None))
            )

            meals_added = tool_result.get("meals_added", 1 if tool_result.get("is_meal") else 0)
            burgers_added = tool_result.get("burgers_added", 0)

            followup_prompt = _format_cart_followup(conversation_context)
            if meals_added > 0 and burgers_added > 0:
                m_word = "meal" if meals_added == 1 else "meals"
                b_word = "burger" if burgers_added == 1 else "burgers"
                return (
                    f"I've added {meals_added} {size} {b_name} {m_word} and {burgers_added} {b_name} {b_word} to your cart. "
                    f"{followup_prompt}"
                )
            elif meals_added > 1:
                return (
                    f"I've added {meals_added} {size} {b_name} meals to your cart. "
                    f"{followup_prompt}"
                )
            elif meals_added == 1:
                meal_prefix = f"{size} {b_name} meal" if b_name else f"{size} meal"
                extras = []
                if side_name and str(side_name).lower() != "none":
                    extras.append(str(side_name))
                if drink_name and str(drink_name).lower() != "none":
                    extras.append(str(drink_name))

                extras_str = f" with {' and '.join(extras)}" if extras else ""
                return (
                    f"Your {meal_prefix}{extras_str} is now in your cart. "
                    f"{followup_prompt}"
                )

        # Single product on product screen
        product_name = tool_result.get("item") or conversation_context.get("selected_product")
        qty_added = tool_result.get("quantity_added", 1)
        partially_added = tool_result.get("partially_added", False)
        followup_prompt = _format_cart_followup(conversation_context)

        if product_name:
            if partially_added:
                return (
                    f"We only have {qty_added} {product_name} in stock, so I've added {qty_added} to your cart. "
                    f"{followup_prompt}"
                )
            elif qty_added > 1:
                item_label = f"{product_name}s" if not product_name.endswith("s") else product_name
                return (
                    f"I've added {qty_added} {item_label} to your cart. "
                    f"{followup_prompt}"
                )
            else:
                return (
                    f"Your {product_name} has been added to your cart. "
                    f"{followup_prompt}"
                )

        if qty_added > 1:
            return (
                f"I've added {qty_added} items to your cart. "
                f"{followup_prompt}"
            )
        return (
            f"Your item has been added to your cart. "
            f"{followup_prompt}"
        )

