import "./Dessertrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useKiosk } from "../context/KioskContext";
import { getSessionId } from "../utils/session";
import { syncScreen } from "../services/screenService";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function Dessert() {
  const navigate = useNavigate();

  const { recommendationData } = useKiosk();
  const [fallbackData, setFallbackData] = useState(() => {
    return (typeof window !== "undefined" && window.__CATEGORY_CACHE__?.['dessert']) || null;
  });

  useEffect(() => {
    syncScreen("recommended_desserts");
    const sid = getSessionId();
    fetch(`${API_BASE_URL}/recommendations/category/dessert?session_id=${sid}`)
      .then((res) => res.json())
      .then((resData) => {
        if (resData && resData.success) {
          const cached = {
            priority: resData.priority,
            premium: resData.premium,
            additional: resData.additional,
          };
          if (typeof window !== "undefined") {
            window.__CATEGORY_CACHE__ = window.__CATEGORY_CACHE__ || {};
            window.__CATEGORY_CACHE__['dessert'] = cached;
          }
          setFallbackData(cached);
        }
      })
      .catch((err) => console.error("Dessert fetch error:", err));
  }, []);

  const isDessertRec =
    recommendationData?.category === "dessert" ||
    recommendationData?.screen === "recommended_desserts" ||
    Boolean(recommendationData?.data?.priority);

  const validRecData = isDessertRec ? recommendationData?.data : null;
  const memoryCache = typeof window !== "undefined" ? window.__CATEGORY_CACHE__?.['dessert'] : null;
  const data = validRecData || fallbackData || memoryCache || {};

  let freshDesserts = data.priority || [];
  let premiumDesserts = data.premium || [];
  let moreDesserts = data.additional || [];

  const allPool = [
    ...(data.priority || []),
    ...(data.premium || []),
    ...(data.additional || []),
    ...(memoryCache?.priority || []),
    ...(memoryCache?.premium || []),
    ...(memoryCache?.additional || []),
  ];
  const dedupedPool = Array.from(new Map(allPool.map(i => [i.id || i.name, i])).values());

  const usedIds = new Set(freshDesserts.map(i => i.id || i.name));
  if (premiumDesserts.length < 2) {
    const cands = dedupedPool.filter(i => !usedIds.has(i.id || i.name));
    premiumDesserts = [...premiumDesserts, ...cands].slice(0, 2);
  }
  premiumDesserts.forEach(i => usedIds.add(i.id || i.name));

  if (moreDesserts.length < 4) {
    const cands = dedupedPool.filter(i => !usedIds.has(i.id || i.name));
    moreDesserts = [...moreDesserts, ...cands].slice(0, 4);
  }
  // Hard guarantee: if still under 4, recycle items from candidate pool so slots never show blank white
  if (moreDesserts.length < 4 && dedupedPool.length > 0) {
    const recycle = dedupedPool.filter(i => !moreDesserts.some(m => (m.id || m.name) === (i.id || i.name)));
    moreDesserts = [...moreDesserts, ...recycle, ...dedupedPool].slice(0, 4);
  }

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

      {/* PRIORITY */}

      {freshDesserts[0] && (
        <ProductCard
          product={freshDesserts[0]}
          variant="large"
          className="card-1"
          badge="popular"
        />
      )}

      {freshDesserts[1] && (
        <ProductCard
          product={freshDesserts[1]}
          variant="large"
          className="card-2"
          badge="popular"
        />
      )}

      {/* PREMIUM */}

      {premiumDesserts[0] && (
        <ProductCard
          product={premiumDesserts[0]}
          variant="large"
          className="card-3"
          badge="premium"
        />
      )}

      {premiumDesserts[1] && (
        <ProductCard
          product={premiumDesserts[1]}
          variant="large"
          className="card-4"
          badge="premium"
        />
      )}

      {/* ADDITIONAL */}

      {moreDesserts[0] && (
        <ProductCard
          product={moreDesserts[0]}
          variant="small"
          className="card-5"
        />
      )}

      {moreDesserts[1] && (
        <ProductCard
          product={moreDesserts[1]}
          variant="small"
          className="card-6"
        />
      )}

      {moreDesserts[2] && (
        <ProductCard
          product={moreDesserts[2]}
          variant="small"
          className="card-7"
        />
      )}

      {moreDesserts[3] && (
        <ProductCard
          product={moreDesserts[3]}
          variant="small"
          className="card-8"
        />
      )}

      {/* TITLES */}

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

      {/* MORE OPTIONS */}

      <div className="more-header">
        <button
          className="view-all-btn"
          onClick={() =>
            navigate("/dessertmenu")
          }
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