/**
 * Category-aware fallback image resolver.
 * Ensures drinks, sides, and desserts never fallback to burger images.
 */
export const getCategoryFallbackImage = (category = "", name = "") => {
  const cat = String(category || "").toLowerCase();
  const n = String(name || "").toLowerCase();

  // Beverages & Drinks
  if (
    cat.includes("drink") ||
    cat.includes("beverage") ||
    cat.includes("caf") ||
    n.includes("coke") ||
    n.includes("cola") ||
    n.includes("coffee") ||
    n.includes("shake") ||
    n.includes("fizz") ||
    n.includes("latte") ||
    n.includes("tea") ||
    n.includes("float") ||
    n.includes("fanta") ||
    n.includes("sprite")
  ) {
    if (n.includes("coffee") || n.includes("latte") || n.includes("frappe")) {
      return "/src/assets/images/Drinks/Classic Cold Coffee.png";
    }
    return "/src/assets/images/Drinks/Coca Cola.png";
  }

  // Sides
  if (
    cat.includes("side") ||
    n.includes("fries") ||
    n.includes("nugget") ||
    n.includes("wing") ||
    n.includes("strip") ||
    n.includes("hashbrown") ||
    n.includes("ring") ||
    n.includes("dip")
  ) {
    return "/src/assets/images/Sides/Fries (Medium).png";
  }

  // Desserts
  if (
    cat.includes("dessert") ||
    n.includes("sundae") ||
    n.includes("softie") ||
    n.includes("mousse") ||
    n.includes("cone") ||
    n.includes("cup") ||
    n.includes("fusion")
  ) {
    return "/src/assets/images/Dessert/Chocolate sundae.png";
  }

  // Default: Burger
  return "/src/assets/images/Burgers/Crispy Veg.png";
};
