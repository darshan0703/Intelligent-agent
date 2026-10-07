import "./Dessertrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";

function Dessert() {
  const navigate = useNavigate();

  const {
    recommendationData,
    setRecommendationData,
  } = useKiosk();

  const { cart } = useCart();

  const [
    fallbackData,
    setFallbackData
  ] = useState(null);

  const [menuItems, setMenuItems] = useState([]);

  // Fetch full category menu once for candidate pool backup
  useEffect(() => {
    let cancelled = false;
    fetch("/menu/desserts")
      .then((res) => res.json())
      .then((sections) => {
        if (!cancelled && Array.isArray(sections)) {
          const all = sections.flatMap((s) => s.products || []);
          setMenuItems(all);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetch("/category/dessert/recommendations")
      .then((res) => res.json())
      .then((resData) => {
        if (!cancelled && resData?.success && resData?.data) {
          setFallbackData(resData.data);
          if (setRecommendationData) {
            setRecommendationData({ data: resData.data });
          }
        }
      })
      .catch((err) => console.warn("Failed to fetch dessert recommendations:", err));

    return () => {
      cancelled = true;
    };
  }, [cart]);

  const data =
    recommendationData?.data ||
    fallbackData ||
    {};

  // ==========================================
  // REAL-TIME CART EXCLUSION FILTER (M7)
  // ==========================================
  const cartNames = useMemo(
    () => new Set((cart || []).map((c) => String(c?.name || "").trim().toLowerCase())),
    [cart]
  );
  const cartIds = useMemo(
    () => new Set((cart || []).map((c) => c?.id).filter(Boolean).map(String)),
    [cart]
  );

  const notInCart = useCallback((item) => {
    if (!item) return false;
    const name = String(item?.name || "").trim().toLowerCase();
    if (cartNames.has(name)) return false;
    if (item?.id && cartIds.has(String(item.id))) return false;
    return true;
  }, [cartNames, cartIds]);

  // Complete pool of eligible candidates for zero-white-card replenishment
  const allCandidatesPool = useMemo(() => {
    const list = [
      ...(data.priority || []),
      ...(data.premium || []),
      ...(data.additional || []),
      ...(data.both?.priority || []),
      ...(data.both?.premium || []),
      ...(data.both?.additional || []),
      ...menuItems,
    ];
    const seen = new Set();
    const deduped = [];
    for (const item of list) {
      if (!item) continue;
      const key = item.id || item.name;
      if (!seen.has(key)) {
        seen.add(key);
        deduped.push(item);
      }
    }
    return deduped;
  }, [data, menuItems]);

  // Dynamic backfill guaranteeing exactly 2 Priority and 2 Premium cards
  const { freshDesserts, premiumDesserts, moreDesserts } = useMemo(() => {
    const usedKeys = new Set();

    // 1. Priority Items (Cards 1 & 2)
    const priority = [];
    for (const item of (data.priority || [])) {
      if (notInCart(item)) {
        const key = item.id || item.name;
        priority.push(item);
        usedKeys.add(key);
        if (priority.length === 2) break;
      }
    }

    if (priority.length < 2) {
      for (const item of (data.additional || [])) {
        if (notInCart(item)) {
          const key = item.id || item.name;
          if (!usedKeys.has(key)) {
            priority.push(item);
            usedKeys.add(key);
            if (priority.length === 2) break;
          }
        }
      }
    }
    if (priority.length < 2) {
      for (const item of allCandidatesPool) {
        if (notInCart(item)) {
          const key = item.id || item.name;
          if (!usedKeys.has(key)) {
            priority.push(item);
            usedKeys.add(key);
            if (priority.length === 2) break;
          }
        }
      }
    }

    // 2. Premium Items (Cards 3 & 4)
    const premium = [];
    for (const item of (data.premium || [])) {
      if (notInCart(item)) {
        const key = item.id || item.name;
        if (!usedKeys.has(key)) {
          premium.push(item);
          usedKeys.add(key);
          if (premium.length === 2) break;
        }
      }
    }

    if (premium.length < 2) {
      const candidatesByPrice = [...allCandidatesPool]
        .filter(notInCart)
        .filter((item) => !usedKeys.has(item.id || item.name))
        .sort((a, b) => (Number(b.price) || 0) - (Number(a.price) || 0));

      for (const item of candidatesByPrice) {
        const key = item.id || item.name;
        premium.push(item);
        usedKeys.add(key);
        if (premium.length === 2) break;
      }
    }

    // 3. Additional Items (Cards 5, 6, 7, 8)
    const additional = [];
    for (const item of (data.additional || [])) {
      if (notInCart(item)) {
        const key = item.id || item.name;
        if (!usedKeys.has(key)) {
          additional.push(item);
          usedKeys.add(key);
          if (additional.length === 4) break;
        }
      }
    }
    if (additional.length < 4) {
      for (const item of allCandidatesPool) {
        if (notInCart(item)) {
          const key = item.id || item.name;
          if (!usedKeys.has(key)) {
            additional.push(item);
            usedKeys.add(key);
            if (additional.length === 4) break;
          }
        }
      }
    }

    return {
      freshDesserts: priority,
      premiumDesserts: premium,
      moreDesserts: additional,
    };
  }, [data, allCandidatesPool, notInCart]);

  return (
    <div className="dessert-page">

      {/* SECTION ICONS */}

      <img
        src={fire}
        alt="fire"
        className="fire-image"
      />

      <img
        src={crown}
        alt="crown"
        className="crown-image"
      />

      {/* HEADER */}

      <Header title="Choose Your Dessert" />

      <BackButton />

      {/* =========================
          PRIORITY DESSERTS
          ========================= */}

      {freshDesserts.slice(0, 2).map((dessert, index) => (
        <ProductCard
          key={dessert.id || `priority-${index}`}
          product={dessert}
          variant="large"
          className={`card-${index + 1}`}
          badge="popular"
        />
      ))}

      {/* =========================
          PREMIUM DESSERTS
          ========================= */}

      {premiumDesserts.slice(0, 2).map((dessert, index) => (
        <ProductCard
          key={dessert.id || `premium-${index}`}
          product={dessert}
          variant="large"
          className={`card-${index + 3}`}
          badge="premium"
        />
      ))}

      {/* =========================
          ADDITIONAL DESSERTS
          ========================= */}

      {moreDesserts.slice(0, 4).map((dessert, index) => (
        <ProductCard
          key={dessert.id || `additional-${index}`}
          product={dessert}
          variant="small"
          className={`card-${index + 5}`}
        />
      ))}

      {/* =========================
          TITLES
          ========================= */}

      <p className="fresh-text">
        Sweet Picks For You
      </p>

      <p className="fresh-text2">
        Popular & perfect for you
      </p>

      <p className="premium-text">
        Premium Desserts
      </p>

      <p className="premium-text2">
        Rich, indulgent & made to delight
      </p>

      <p className="more-text">
        More Dessert Options
      </p>

      {/* =========================
          MORE OPTIONS
          ========================= */}

      <div className="more-header">
        <button
          className="view-all-btn"
          onClick={() => navigate("/dessertmenu")}
        >
          View All Desserts →
        </button>
      </div>

      {/* CART */}

      <CartContainer />

      {/* FOOTER */}

      <FooterDecoration />

    </div>
  );
}

export default Dessert;