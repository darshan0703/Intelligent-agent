import { createContext, useContext, useState, useRef, useMemo, useEffect } from "react";
import {
  computeDisplayCart,
  loadSavedOrder,
  loadSavedSnapshot,
  saveOrder,
  saveSnapshot,
  resetCartOrder,
} from "../utils/cartOrdering";

const CartContext = createContext();

export function CartProvider({ children }) {
  const [cart, setCart] = useState([]);
  const [itemCount, setItemCount] = useState(0);
  const [total, setTotal] = useState(0);

  const [cartAddEvent, setCartAddEvent] = useState(0);
  const lastHandledAddEventRef = useRef(0);
  const cartScrollTopRef = useRef(0);

  // Single centralized displayCart ordering across the application
  const { displayCart, newOrder, newSnapshot } = useMemo(() => {
    return computeDisplayCart(cart, loadSavedOrder(), loadSavedSnapshot());
  }, [cart]);

  // Synchronize order and quantity snapshots to sessionStorage
  useEffect(() => {
    if (cart.length === 0) {
      resetCartOrder();
    } else {
      saveOrder(newOrder);
      saveSnapshot(newSnapshot);
    }
  }, [cart, newOrder, newSnapshot]);

  const syncCart = (data) => {
    console.log("SYNC CART", data);
    setCart(data.cart || []);
    setItemCount(data.itemCount || 0);
    setTotal(data.total || 0);
  };

  const notifyCartItemAdded = () => {
    setCartAddEvent((prev) => prev + 1);
  };

  const isCartAddEventPending = () => {
    return cartAddEvent > 0 && cartAddEvent > lastHandledAddEventRef.current;
  };

  const markCartAddEventHandled = () => {
    lastHandledAddEventRef.current = cartAddEvent;
  };

  const setCartScrollTop = (val) => {
    cartScrollTopRef.current = typeof val === "number" ? val : 0;
  };

  console.log("Cart:", itemCount, total);

  const clearCart = () => {
    setCart([]);
    setItemCount(0);
    setTotal(0);
    cartScrollTopRef.current = 0;
    resetCartOrder();
  };

  return (
    <CartContext.Provider
      value={{
        cart,
        displayCart,
        itemCount,
        total,
        syncCart,
        clearCart,
        cartAddEvent,
        notifyCartItemAdded,
        isCartAddEventPending,
        markCartAddEventHandled,
        get cartScrollTop() {
          return cartScrollTopRef.current;
        },
        getCartScrollTop: () => cartScrollTopRef.current,
        setCartScrollTop,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  return useContext(CartContext);
}