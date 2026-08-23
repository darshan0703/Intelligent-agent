import "./CartContainer.css";
import { useCart } from "../context/CartContext";
import { useNavigate } from "react-router-dom";

function CartContainer() {

  const navigate = useNavigate();

  const {
    cart,
    itemCount,
    total
  } = useCart();

  console.log(cart);

  const handleReviewPay = () => {

    if (itemCount === 0) {
      return;
    }

    navigate("/Cart");

  };

  return (

    <div className="cart-container">

      {/* ========================================= */}
      {/* TOP BAR */}
      {/* ========================================= */}

      <div className="cart-header">

        {/* LEFT */}

        <div className="cart-left">

          <span className="cart-icon">
            🛒
          </span>

          <p className="Your-cart">
            Your Cart
          </p>

          <p className="cart-count">
            ({itemCount} items)
          </p>

        </div>

      </div>


      {/* ========================================= */}
      {/* CART ITEMS */}
      {/* ========================================= */}

      <div className="cart-items">

        {cart.map((item, index) => (

          <div
            key={index}
            className="cart-item"
          >

            <div className="cart-item-header">

              {/* ITEM NAME */}

              <div className="cart-item-name">

                {item.name}

              </div>


              {/* QUANTITY */}

              <div className="cart-item-qty">

                x{item.quantity}

              </div>


              {/* ITEM PRICE */}

              <div className="cart-item-price">

                ₹{item.subtotal}

              </div>

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


      {/* ========================================= */}
      {/* EMPTY CART MESSAGE */}
      {/* ========================================= */}

      {itemCount === 0 && (

        <p className="No-items">
          NO ITEMS ADDED
        </p>

      )}


      {/* ========================================= */}
      {/* TOTAL */}
      {/* ========================================= */}

<div className="cart-footer">

  <p className="total-text">
    Total
  </p>

  {itemCount > 0 ? (

    <button
      className="review-pay-btn"
      onClick={handleReviewPay}
    >
      <span>
        Review & Pay
      </span>

      <span>
        ₹ {total}/-
      </span>
    </button>

  ) : (

    <p className="total-price">
      ₹ {total}/-
    </p>

  )}

</div>

      {/* ========================================= */}
      {/* DIVIDER */}
      {/* ========================================= */}

      <div className="thin-line"></div>

    </div>

  );

}

export default CartContainer;