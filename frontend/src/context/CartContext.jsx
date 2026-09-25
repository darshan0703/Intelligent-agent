import { createContext, useContext, useState, useEffect } from "react";
import { getSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

const CartContext = createContext();

export function CartProvider({ children }) {

  const [cart, setCart] = useState([]);
  const [itemCount, setItemCount] = useState(0);
  const [total, setTotal] = useState(0);

  const syncCart = (data) => {
    console.log("SYNC CART", data);
    setCart(data.cart || []);
    setItemCount(data.itemCount || 0);
    setTotal(data.total || 0);
  };

  const refreshCart = async () => {
    try {
      const sessionId = getSessionId();
      const res = await fetch(`${API_BASE_URL}/cart?session_id=${sessionId}`);
      const data = await res.json();
      if (data.success) {
        setCart(data.cart || []);
        setItemCount(data.itemCount || 0);
        setTotal(data.total || 0);
      }
    } catch (err) {
      console.error("Cart refresh error:", err);
    }
  };

  useEffect(() => {
    refreshCart();
  }, []);

  const addItemOptimistic = (item, quantity = 1) => {
    if (!item) return;
    const price = parseFloat(item.price || item.unitPrice || 0);

    // 1. Instant local optimistic update (0ms response)
    setCart((prevCart) => {
      const idx = prevCart.findIndex(
        (p) => p.name === item.name || (p.item_id && item.id && p.item_id === item.id)
      );
      if (idx > -1) {
        const next = [...prevCart];
        const existing = next[idx];
        const newQty = (existing.quantity || 1) + quantity;
        next[idx] = {
          ...existing,
          quantity: newQty,
          subtotal: Math.round((existing.unitPrice || price) * newQty * 100) / 100,
        };
        return next;
      }
      return [
        ...prevCart,
        {
          line_id: "opt-" + Date.now(),
          item_id: item.id || item.item_id,
          name: item.name,
          quantity: quantity,
          unitPrice: price,
          price: price,
          subtotal: Math.round(price * quantity * 100) / 100,
          image: item.image,
          type: item.type || "item",
          category: item.category,
        },
      ];
    });
    setItemCount((prev) => prev + quantity);
    setTotal((prev) => Math.round((prev + price * quantity) * 100) / 100);

    // 2. Background server sync
    fetch(`${API_BASE_URL}/cart/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: getSessionId(),
        item_name: item.name,
        item_id: item.id || item.item_id,
        quantity,
        offer_price: item.has_micro_deal ? item.offer_price || price : undefined,
        deal_tag: item.deal_tag,
        has_micro_deal: item.has_micro_deal,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data && data.success) {
          syncCart(data);
        }
      })
      .catch((err) => {
        console.error("Optimistic cart sync error:", err);
        refreshCart();
      });
  };

  const [winbackOffer, setWinbackOffer] = useState(null);

  const clearWinbackOffer = () => {
    setWinbackOffer(null);
  };

  const checkWinback = async () => {
    try {
      const sessionId = getSessionId();
      const res = await fetch(`${API_BASE_URL}/recommendations/winback?session_id=${sessionId}`);
      const data = await res.json();
      if (data && data.success && data.has_winback && data.winback_item) {
        setWinbackOffer(data);
      }
    } catch (err) {
      console.warn("Winback fetch error:", err);
    }
  };

  const updateItem = async (itemIndex, action) => {
    const isRemoving = action === "delete" || (action === "decrease" && cart[itemIndex]?.quantity <= 1);
    try {
      const sessionId = getSessionId();
      const response = await fetch(`${API_BASE_URL}/cart/item`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_index: itemIndex, action, session_id: sessionId }),
      });
      const data = await response.json();
      if (data.success) {
        syncCart(data);
        if (isRemoving) {
          checkWinback();
        }
      }
    } catch (error) {
      console.error("Failed to update cart:", error);
      refreshCart();
    }
  };

  const clearCart = () => {
    setCart([]);
    setItemCount(0);
    setTotal(0);
    setWinbackOffer(null);
    fetch(`${API_BASE_URL}/cart?session_id=${getSessionId()}`, { method: "DELETE" }).catch(() => {});
  };

  return (
    <CartContext.Provider
      value={{
        cart,
        itemCount,
        total,
        syncCart,
        refreshCart,
        clearCart,
        addItemOptimistic,
        updateItem,
        winbackOffer,
        clearWinbackOffer,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  return useContext(CartContext);
}