import "./CartContainer.css";

function CartContainer({ itemCount, total }) {

  return (

    <div className="cart-container">

      {/* TOP BAR */}
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

        {/* RIGHT */}
        <div className="cart-right">

          <span className="edit-icon">
            ✏️
          </span>

          <p className="edit-text">
            Edit Cart
          </p>

        </div>

      </div>

      {/* TOTAL */}
      <div className="cart-footer">

        <p className="total-text">
          Total
        </p>

{itemCount === 0 && (

  <p className="No-items">
    NO ITEM ADDED
  </p>

)}

        <p className="total-price">
          ₹ {total}/-
        </p>

      </div>
      <div className="thin-line"></div>

    </div>
  );
}

export default CartContainer;