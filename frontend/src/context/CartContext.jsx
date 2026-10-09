import { createContext, useContext, useState, useRef } from "react";

const CartContext = createContext();

export function CartProvider({ children }) {

  const [cart, setCart] = useState([]);

  const [itemCount, setItemCount] = useState(0);

  const [total, setTotal] = useState(0);

  const [cartAddEvent, setCartAddEvent] = useState(0);
  const lastHandledAddEventRef = useRef(0);
  const cartScrollTopRef = useRef(0);

const syncCart = (data) => {

  console.log("SYNC CART", data);

  setCart(data.cart);
  setItemCount(data.itemCount);
  setTotal(data.total);

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

  };

  return (

    <CartContext.Provider
      value={{
        cart,
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
        setCartScrollTop
      }}
    >

      {children}

    </CartContext.Provider>

  );

}

export function useCart() {

  return useContext(CartContext);

}