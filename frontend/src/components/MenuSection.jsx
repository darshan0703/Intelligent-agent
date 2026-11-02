import "./MenuSection.css";
import { useMemo } from "react";
import ProductCard from "./ProductCard";
import { useCart } from "../context/CartContext";
import { getOrderedProductIds, getOrderedProductNames } from "../utils/cartUtils";

function MenuSection({ title, products }) {
  const { cart } = useCart();

  const orderedProductIds = useMemo(() => getOrderedProductIds(cart), [cart]);
  const orderedProductNames = useMemo(() => getOrderedProductNames(cart), [cart]);

  const isItemInCart = (product) => {
    if (!product) return false;
    if (product.id != null && orderedProductIds.has(String(product.id))) return true;
    const name = String(product.name || "").trim().toLowerCase();
    return orderedProductNames.has(name);
  };

  // Keep items not in cart first (original order), and push added cart items to the end
  const sortedProducts = [...(products || [])].sort((a, b) => {
    const aInCart = isItemInCart(a) ? 1 : 0;
    const bInCart = isItemInCart(b) ? 1 : 0;
    return aInCart - bInCart;
  });

  return (
    <div className="menu-section">
      <h2 className="menu-section-title">{title}</h2>

      <div className="menu-section-grid">
        {sortedProducts.map((product) => (
          <ProductCard
            key={product.id}
            product={product}
            variant="menu"
            badge={product.badge}
          />
        ))}
      </div>
    </div>
  );
}

export default MenuSection;