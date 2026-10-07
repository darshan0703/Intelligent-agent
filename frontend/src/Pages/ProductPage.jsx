import "./ProductPage.css";

import { useState, useEffect, useRef } from "react";
import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";
import { useLocation, useNavigate } from "react-router-dom";
import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";
import MealPopup from "../components/MealPopup";
import FooterDecoration from "../components/FooterDecoration";
import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

function ProductPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const origin = location.state?.origin || "/";

  const {
    productData,
    setProductData,
    mealData,
    setMealData,
    mealPopupOpen,
    setMealPopupOpen,
    foodPreference,
  } = useKiosk();

  const { cart, syncCart } = useCart();
  const product = productData?.data?.product;
  const [recommendations, setRecommendations] = useState(
    productData?.data?.recommendations || []
  );
  const refreshTimersRef = useRef({});
  const [quantity, setQuantity] = useState(1);

  // Meal upgrades are available only for burger products.
  const isBurger =
    product?.category?.toLowerCase() === "burger" ||
    product?.category?.toLowerCase() === "burgers";

  const getDismissedKey = () => {
    const sessionId =
      localStorage.getItem("session_id") || "default";
    return `dismissed_meals_${sessionId}`;
  };

  const isProductDismissed = (productId) => {
    try {
      const dismissed = JSON.parse(
        sessionStorage.getItem(getDismissedKey()) || "[]"
      );
      return dismissed.includes(productId);
    } catch {
      return false;
    }
  };

  const dismissProduct = (productId) => {
    try {
      const dismissed = JSON.parse(
        sessionStorage.getItem(getDismissedKey()) || "[]"
      );

      if (!dismissed.includes(productId)) {
        sessionStorage.setItem(
          getDismissedKey(),
          JSON.stringify([...dismissed, productId])
        );
      }
    } catch {
      // Ignore sessionStorage errors.
    }
  };

  const checkMealOffer = async ({
    automatic = false,
    productId = product?.id,
    signal,
  } = {}) => {
    if (!product || !isBurger) return;

    const requestedProductId = productId;

    try {
      const response = await fetch("/meal/options", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_id: requestedProductId,
          food_preference: foodPreference,
          cart,
        }),
        signal,
      });

      const data = await response.json();

      if (signal?.aborted || product?.id !== requestedProductId) {
        return;
      }

      if (data.success && data.is_meal_available) {
        if (automatic && isProductDismissed(requestedProductId)) {
          setMealPopupOpen(false);
          return;
        }

        setMealData(data);
        setMealPopupOpen(true);
      } else {
        setMealPopupOpen(false);
      }
    } catch (error) {
      if (error.name === "AbortError") return;

      console.error("Failed to load meal offer:", error);

      if (product?.id === requestedProductId) {
        setMealPopupOpen(false);
      }
    }
  };

  useEffect(() => {
    if (!product) return;

    if (!isBurger) {
      setMealPopupOpen(false);
      setMealData(null);
      return;
    }

    const controller = new AbortController();
    const currentProductId = product.id;

    setMealPopupOpen(false);
    setMealData(null);

    if (!isProductDismissed(currentProductId)) {
      checkMealOffer({
        automatic: true,
        productId: currentProductId,
        signal: controller.signal,
      });
    }

    return () => {
      controller.abort();
    };
  }, [product?.id, isBurger]);

  useEffect(() => {
    return () => {
      Object.values(refreshTimersRef.current).forEach((timer) => clearTimeout(timer));
    };
  }, []);

  useEffect(() => {
    if (!product?.name) return;

    const controller = new AbortController();

    fetch(`/menu/product/${encodeURIComponent(product.name)}/recommendations`, {
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (data && data.recommendations) {
          setRecommendations(data.recommendations);
        }
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          console.error("Failed to load recommendations:", error);
        }
      });

    return () => {
      controller.abort();
    };
  }, [product?.name]);

  const handleRecommendClick = (item) => {
    setProductData({
      screen: "product",
      data: {
        product: item,
        recommendations: [],
      },
    });
    navigate("/product", {
      state: {
        origin: location.pathname,
      },
    });
  };

  const handleDirectAddRecommend = async (e, item) => {
    e.stopPropagation();

    try {
      const response = await fetch("/cart/add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_name: item.name,
          quantity: 1,
        }),
      });

      const data = await response.json();
      if (data && data.cart) {
        syncCart(data);
      }
    } catch (error) {
      console.error("Failed to add recommended item directly to cart:", error);
    }

    // Reset/start the 10-second silent refresh timer for this card
    if (refreshTimersRef.current[item.id]) {
      clearTimeout(refreshTimersRef.current[item.id]);
    }

    refreshTimersRef.current[item.id] = setTimeout(async () => {
      try {
        const res = await fetch(
          `/menu/product/${encodeURIComponent(product.name)}/recommendations`
        );
        if (res.ok) {
          const freshData = await res.json();
          if (freshData && freshData.recommendations) {
            setRecommendations(freshData.recommendations);
          }
        }
      } catch (err) {
        console.error("Silent refresh error:", err);
      } finally {
        delete refreshTimersRef.current[item.id];
      }
    }, 10000);
  };

  const handleMealButtonClick = () => {
    if (!isBurger) return;

    if (
      mealData?.success &&
      mealData?.is_meal_available
    ) {
      setMealPopupOpen(true);
      return;
    }

    checkMealOffer({
      automatic: false,
      productId: product.id,
    });
  };

  const handleContinue = (mealSize) => {
    navigate("/mealpage", {
      state: {
        meal: mealData.meals[mealSize],
        origin: origin,
      },
    });
  };

  if (!product) {
    return (
      <div className="product-page">
        <Header title="Product Details" />
        <PreviousButton />
        <h2
          style={{
            textAlign: "center",
            marginTop: "200px",
          }}
        >
          No product selected.
        </h2>
      </div>
    );
  }

  const handleAddToCart = async () => {
    try {
      const response = await fetch("/cart/add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          item_name: product.name,
          quantity: quantity,
        }),
      });

      const data = await response.json();

      if (data.success) {
        syncCart(data);
        // Navigate back smoothly without full page refresh
        navigate(origin);
      }
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="product-page">
      <Header title="Product Details" />
      <PreviousButton />

      <img
        src={product.image}
        alt={product.name}
        className="product-image"
      />

      <div className="product-title-container">
        <h1 className="product-name">
          {(() => {
            const words = product.name.split(" ");
            const midpoint = Math.ceil(words.length / 2);

            return (
              <>
                {words.slice(0, midpoint).join(" ")}
                <br />
                {words.slice(midpoint).join(" ")}
              </>
            );
          })()}

          {product.foodType && (
            <img
              src={
                product.foodType === "veg"
                  ? vegIcon
                  : nonVegIcon
              }
              alt={product.foodType}
              className="product-type-icon"
            />
          )}
        </h1>
      </div>

      <p className="product-short-description">
        {product.shortDescription}
      </p>

      <div className="product-price-row">
        <p className="product-price">
          ₹ {product.price}
        </p>

        {isBurger && (
          <button
            className="meal-upgrade-btn"
            onClick={handleMealButtonClick}
          >
            Upgrade to a Meal
          </button>
        )}
      </div>

      <h2 className="section-title about-title">
        About This Item
      </h2>

      <p className="product-description">
        {product.longDescription}
      </p>

      <h2 className="section-title recommended-title">
        Recommended With
      </h2>

      <div className="recommendations">
        {recommendations.map((item) => (
          <div
            key={item.id}
            className="recommend-card"
            onClick={() => handleRecommendClick(item)}
            title={`View ${item.name}`}
          >
            {item.image && (
              <img
                src={item.image.startsWith("/") || item.image.startsWith("http") ? item.image : `/${item.image}`}
                alt={item.name}
                className="recommend-card-img"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            )}
            <div className="recommend-card-info">
              <span className="recommend-card-name" title={item.name}>
                {item.name}
              </span>
              <span className="recommend-card-price">₹ {item.price}</span>
            </div>
            <button
              type="button"
              className="recommend-card-add-btn"
              onClick={(e) => handleDirectAddRecommend(e, item)}
              title={`Add ${item.name} to Cart`}
            >
              +
            </button>
          </div>
        ))}
      </div>

      <div className="quantity-selector">
        <button
          className="qty-btn"
          onClick={() =>
            setQuantity((prev) =>
              prev > 1 ? prev - 1 : 1
            )
          }
        >
          −
        </button>

        <span className="qty-value">{quantity}</span>

        <button
          className="qty-btn"
          onClick={() =>
            setQuantity((prev) => prev + 1)
          }
        >
          +
        </button>
      </div>

      <button
        className="add-cart-btn"
        onClick={handleAddToCart}
      >
        {`Add To Cart • ₹ ${
          product.price * quantity
        }`}
      </button>

      <CartContainer />

      {isBurger && (
        <MealPopup
          open={mealPopupOpen}
          meals={mealData}
          onClose={() => {
            dismissProduct(product.id);
            setMealPopupOpen(false);
          }}
          onContinue={handleContinue}
        />
      )}

      <FooterDecoration />
    </div>
  );
}

export default ProductPage;
