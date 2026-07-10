import { createContext, useContext, useState } from "react";

const CartContext = createContext();

export function CartProvider({ children }) {

  const [cart, setCart] = useState([]);

  const [itemCount, setItemCount] = useState(0);

  const [total, setTotal] = useState(0);

const syncCart = (data) => {

  console.log("SYNC CART", data);

  setCart(data.cart);
  setItemCount(data.itemCount);
  setTotal(data.total);

};

console.log("Cart:", itemCount, total);

  const clearCart = () => {

    setCart([]);

    setItemCount(0);

    setTotal(0);

  };

  return (

    <CartContext.Provider
      value={{
        cart,
        itemCount,
        total,
        syncCart,
        clearCart
      }}
    >

      {children}

    </CartContext.Provider>

  );

}

export function useCart() {

  return useContext(CartContext);

}