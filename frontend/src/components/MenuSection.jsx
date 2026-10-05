import "./MenuSection.css";
import ProductCard from "./ProductCard";
import { useCart } from "../context/CartContext";

function MenuSection({ title, products }) {
  const { cart } = useCart();

  const cartIds = new Set((cart || []).map((c) => c.id).filter(Boolean));
  const cartNames = new Set(
    (cart || []).map((c) => String(c.name || "").trim().toLowerCase())
  );

  const isItemInCart = (product) => {
    if (product.id && cartIds.has(product.id)) return true;
    const name = String(product.name || "").trim().toLowerCase();
    return cartNames.has(name);
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