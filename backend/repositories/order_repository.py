from database import supabase

BRANCH_ID = 1

def complete_order(cart):
    try:
        requirements = []

        # Build list of items to deduct
        for item in cart:
            quantity = item["quantity"]

            if item["type"] == "meal":
                requirements.extend([
                    (item["main_item"]["id"], quantity),
                    (item["side"]["id"], quantity),
                    (item["drink"]["id"], quantity),
                ])
            else:
                requirements.append((item["id"], quantity))

        # Check inventory first
        current_stock = {}

        for item_id, quantity in requirements:
            response = (
                supabase.table("inventory")
                .select("stock")
                .eq("item_id", item_id)
                .eq("branch_id", BRANCH_ID)
                .single()
                .execute()
            )

            if not response.data:
                return {
                    "success": False,
                    "message": f"Inventory not found for item {item_id}."
                }

            stock = response.data["stock"]

            if stock < quantity:
                return {
                    "success": False,
                    "message": f"Not enough stock for item {item_id}."
                }

            current_stock[item_id] = stock

        # Deduct inventory
        for item_id, quantity in requirements:
            new_stock = current_stock[item_id] - quantity

            (
                supabase.table("inventory")
                .update({"stock": new_stock})
                .eq("item_id", item_id)
                .eq("branch_id", BRANCH_ID)
                .execute()
            )

        return {
            "success": True,
            "message": "Order completed successfully."
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }