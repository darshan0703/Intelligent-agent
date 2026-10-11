import "./CartContainer.css";
import { useRef, useEffect, useMemo } from "react";
import { useCart } from "../context/CartContext";
import { useNavigate } from "react-router-dom";

const getCartItemKey = (item) => {
  if (item.type === "meal") {
    return `meal_${item.name}_${item.side?.id}_${item.drink?.id}`;
  }
  return `item_${item.id || item.name}`;
};

const loadSavedOrder = () => {
  try {
    const raw = sessionStorage.getItem("cart_item_order");
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

const saveOrder = (order) => {
  try {
    sessionStorage.setItem("cart_item_order", JSON.stringify(order));
  } catch {
    // Ignore sessionStorage errors
  }
};

// Module-level persistent key order and cart snapshot across component remounts
let persistentOrderKeys = [];
let prevCartSnapshot = [];

function CartContainer() {
  const navigate = useNavigate();

  const {
    cart,
    itemCount,
    total,
    cartAddEvent,
    isCartAddEventPending,
    markCartAddEventHandled,
    cartScrollTop,
    getCartScrollTop,
    setCartScrollTop,
  } = useCart();

  const count = Number(itemCount) || 0;
  const cartTotal = Number(total) || 0;
  const isEmpty = count === 0;

  const cartItemsRef = useRef(null);
  const isRestoredRef = useRef(false);

  // Maintain display order: moving newly added or quantity-increased items to the bottom
  const displayCart = useMemo(() => {
    if (!cart || cart.length === 0) {
      persistentOrderKeys = [];
      prevCartSnapshot = [];
      saveOrder([]);
      return [];
    }

    const currentKeysSet = new Set(cart.map(getCartItemKey));
    let order = persistentOrderKeys.length > 0 ? persistentOrderKeys : loadSavedOrder();
    order = order.filter((k) => currentKeysSet.has(k));

    // Detect which item was newly added or had its quantity increased
    if (prevCartSnapshot.length > 0) {
      const prevQtyMap = new Map();
      for (const p of prevCartSnapshot) {
        prevQtyMap.set(getCartItemKey(p), p.quantity || 0);
      }

      let updatedKey = null;
      for (const item of cart) {
        const key = getCartItemKey(item);
        const prevQty = prevQtyMap.get(key) || 0;
        if (item.quantity > prevQty) {
          updatedKey = key;
          break;
        }
      }

      if (updatedKey) {
        order = order.filter((k) => k !== updatedKey);
        order.push(updatedKey);
      }
    }

    // Ensure any newly added or remaining keys in cart are present in order
    for (const item of cart) {
      const k = getCartItemKey(item);
      if (!order.includes(k)) {
        order.push(k);
      }
    }

    persistentOrderKeys = order;
    prevCartSnapshot = cart;
    saveOrder(order);

    const itemMap = new Map();
    for (const item of cart) {
      itemMap.set(getCartItemKey(item), item);
    }

    const result = [];
    for (const k of order) {
      const item = itemMap.get(k);
      if (item) {
        result.push(item);
      }
    }

    return result;
  }, [cart]);

  // Restore saved scroll position on mount/remount (when no add event is pending)
  useEffect(() => {
    if (isEmpty) {
      return;
    }

    if (isCartAddEventPending && isCartAddEventPending()) {
      isRestoredRef.current = true;
      return;
    }

    if (isRestoredRef.current) {
      return;
    }

    const savedTop = getCartScrollTop ? getCartScrollTop() : cartScrollTop;
    if (savedTop <= 0) {
      isRestoredRef.current = true;
      return;
    }

    let rafId;
    const applyRestore = () => {
      if (cartItemsRef.current) {
        cartItemsRef.current.scrollTop = savedTop;
        isRestoredRef.current = true;
      }
    };

    applyRestore();
    rafId = requestAnimationFrame(applyRestore);

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [isEmpty, cart]);

  // Handle successful-add auto-scroll
  useEffect(() => {
    if (!isCartAddEventPending || !isCartAddEventPending()) {
      return;
    }

    let rafId1;
    let rafId2;

    rafId1 = requestAnimationFrame(() => {
      rafId2 = requestAnimationFrame(() => {
        if (cartItemsRef.current) {
          cartItemsRef.current.scrollTo({
            top: cartItemsRef.current.scrollHeight,
            behavior: "smooth",
          });
          if (setCartScrollTop) {
            setCartScrollTop(cartItemsRef.current.scrollHeight);
          }
          if (markCartAddEventHandled) {
            markCartAddEventHandled();
          }
        }
      });
    });

    return () => {
      if (rafId1) cancelAnimationFrame(rafId1);
      if (rafId2) cancelAnimationFrame(rafId2);
    };
  }, [cartAddEvent, cart, isCartAddEventPending, markCartAddEventHandled, setCartScrollTop]);

  const handleScroll = (e) => {
    if (e.target && setCartScrollTop) {
      setCartScrollTop(e.target.scrollTop);
    }
  };

  const handleReviewPay = () => {
    if (count === 0) {
      return;
    }
    navigate("/Cart");
  };

  return (
    <div className={`cart-container ${isEmpty ? "empty" : "expanded"}`}>
      {/* ========================================= */}
      {/* TOP BAR / HEADER */}
      {/* ========================================= */}

      <div className="cart-header">
        {/* LEFT */}
        <div className="cart-left">
          <span className="cart-icon">🛒</span>
          <p className="Your-cart">Your Cart</p>
          <p className="cart-count">
            ({count} {count === 1 ? "item" : "items"})
          </p>
        </div>

        {/* WHEN EMPTY: Show inline Total & ₹ 0/- on the right in one line */}
        {isEmpty && (
          <div className="cart-inline-total">
            <span className="inline-total-label">Total</span>
            <span className="inline-total-price">₹ 0/-</span>
          </div>
        )}
      </div>


      {/* ========================================= */}
      {/* CART ITEMS (Only shown when expanded) */}
      {/* ========================================= */}

      {!isEmpty && (
        <div className="cart-items" ref={cartItemsRef} onScroll={handleScroll}>
          {displayCart.map((item) => (
            <div key={getCartItemKey(item)} className="cart-item">
              <div className="cart-item-header">
                {/* ITEM NAME */}
                <div className="cart-item-name">{item.name}</div>

                {/* QUANTITY */}
                <div className="cart-item-qty">x{item.quantity}</div>

                {/* ITEM PRICE */}
                <div className="cart-item-price">₹{item.subtotal}</div>
              </div>

              {/* MEAL DETAILS */}
              {item.type === "meal" && (
                <div className="cart-meal-items">
                  (includes {item.side?.name} + {item.drink?.name})
                </div>
              )}
            </div>
          ))}
        </div>
      )}


      {/* ========================================= */}
      {/* EMPTY CART MESSAGE */}
      {/* ========================================= */}

      {isEmpty && (
        <p className="No-items">
          NO ITEMS ADDED
        </p>
      )}


      {/* ========================================= */}
      {/* TOTAL / FOOTER (Only when expanded) */}
      {/* ========================================= */}

      {!isEmpty && (
        <div className="cart-footer">
          <p className="total-text">Total</p>
          <button
            className="review-pay-btn"
            onClick={handleReviewPay}
          >
            <span>Review & Pay</span>
            <span>₹ {cartTotal.toLocaleString("en-IN")}/-</span>
          </button>
        </div>
      )}


      {/* ========================================= */}
      {/* DIVIDER */}
      {/* ========================================= */}

      {!isEmpty && <div className="thin-line"></div>}
    </div>
  );
}

export default CartContainer;