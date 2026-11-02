/**
 * Utility functions for extracting ordered product identifiers from cart.
 *
 * Distinguishes between standalone products (item.id) and combo meals (item.main_item.id).
 * For meal items, extracts the burger ID from main_item.id / burger.id.
 * Side and drink IDs from meals are not treated as burger IDs in burger recommendation ranking.
 */

/**
 * Extracts ordered product IDs from the cart for display and recommendation ranking.
 *
 * @param {Array} cart - Cart item array
 * @returns {Set<string>} - Set of stringified product IDs
 */
export function getOrderedProductIds(cart) {
  return new Set(
    (cart || [])
      .flatMap((item) => {
        if (item?.type === "meal") {
          const main = item.main_item || item.burger;
          return [main?.id];
        }
        return [item?.id];
      })
      .filter((id) => id != null && id !== "")
      .map(String)
  );
}

/**
 * Extracts normalized ordered product names from the cart for display and recommendation ranking.
 *
 * @param {Array} cart - Cart item array
 * @returns {Set<string>} - Set of lowercase trimmed product names
 */
export function getOrderedProductNames(cart) {
  const names = new Set();
  for (const item of cart || []) {
    if (!item) continue;
    if (item.type === "meal") {
      const main = item.main_item || item.burger;
      if (main?.name) {
        names.add(String(main.name).trim().toLowerCase());
      }
      if (item.name) {
        const norm = String(item.name).trim().toLowerCase();
        names.add(norm);
        for (const suffix of [" regular meal", " medium meal", " large meal", " meal"]) {
          if (norm.endsWith(suffix)) {
            names.add(norm.slice(0, -suffix.length).trim());
          }
        }
      }
    } else if (item.name) {
      names.add(String(item.name).trim().toLowerCase());
    }
  }
  return names;
}
