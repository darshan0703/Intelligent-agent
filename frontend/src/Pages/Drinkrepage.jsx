import "./Drinkrepage.css";

import { useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";
import Menufilters from "../components/Menufilters";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useKiosk } from "../context/KioskContext";
import { getSessionId } from "../utils/session";
import { syncScreen } from "../services/screenService";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function Drink() {
  const navigate = useNavigate();
  const { recommendationData } = useKiosk();

  const [selectedType, setSelectedType] = useState("both");

  const [fallbackData, setFallbackData] = useState(() => {
    return (typeof window !== "undefined" && window.__CATEGORY_CACHE__?.['drink']) || null;
  });

  useEffect(() => {
    syncScreen("recommended_drinks");
    const sid = getSessionId();
    fetch(`${API_BASE_URL}/recommendations/category/drink?session_id=${sid}`)
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
            window.__CATEGORY_CACHE__['drink'] = cached;
          }
          setFallbackData(cached);
        }
      })
      .catch((err) => console.error("Drink fetch error:", err));
  }, []);

  const isDrinkRec =
    recommendationData?.category === "drink" ||
    recommendationData?.screen === "recommended_drinks" ||
    Boolean(recommendationData?.data?.priority);

  const memoryCache = (typeof window !== "undefined" && window.__CATEGORY_CACHE__?.['drink']) || null;
  const validRecData = isDrinkRec ? recommendationData?.data : null;
  const data = validRecData || fallbackData || memoryCache || {};

  const allDrinks = {
    priority: data.priority || [],
    premium: data.premium || [],
    additional: data.additional || [],
  };

  const filterProducts = useCallback(
    (products) => {
      if (!products || !Array.isArray(products)) return [];
      if (selectedType === "both") {
        return products;
      }
      return products.filter(
        (product) =>
          (product.type || product.serving_type || "").toLowerCase() === selectedType
      );
    },
    [selectedType]
  );

  let freshDrinks = filterProducts(allDrinks.priority);
  let premiumDrinks = filterProducts(allDrinks.premium);
  let moreDrinks = filterProducts(allDrinks.additional);

  // Pool of all candidate items for defensive backfill
  const allPool = [
    ...(allDrinks.priority || []),
    ...(allDrinks.premium || []),
    ...(allDrinks.additional || []),
    ...(fallbackData?.priority || []),
    ...(fallbackData?.premium || []),
    ...(fallbackData?.additional || []),
    ...(memoryCache?.priority || []),
    ...(memoryCache?.premium || []),
    ...(memoryCache?.additional || []),
  ];
  const filteredPool = filterProducts(allPool);
  const dedupedFiltered = Array.from(new Map(filteredPool.map(i => [i.id || i.name, i])).values());
  const dedupedAll = Array.from(new Map(allPool.map(i => [i.id || i.name, i])).values());

  const usedIds = new Set(freshDrinks.map(i => i.id || i.name));

  // Ensure priority has at least 2 cards
  if (freshDrinks.length < 2) {
    const pool = dedupedFiltered.length >= 2 ? dedupedFiltered : dedupedAll;
    const cands = pool.filter(i => !usedIds.has(i.id || i.name));
    freshDrinks = [...freshDrinks, ...cands].slice(0, 2);
    freshDrinks.forEach(i => usedIds.add(i.id || i.name));
  }

  // Ensure premium has at least 2 cards
  if (premiumDrinks.length < 2) {
    const pool = dedupedFiltered.length >= 4 ? dedupedFiltered : dedupedAll;
    const cands = pool.filter(i => !usedIds.has(i.id || i.name));
    premiumDrinks = [...premiumDrinks, ...cands].slice(0, 2);
  }
  premiumDrinks.forEach(i => usedIds.add(i.id || i.name));

  // Ensure additional has at least 4 cards (never blank)
  if (moreDrinks.length < 4) {
    const pool = dedupedFiltered.length >= 6 ? dedupedFiltered : dedupedAll;
    const cands = pool.filter(i => !usedIds.has(i.id || i.name));
    moreDrinks = [...moreDrinks, ...cands].slice(0, 4);
  }
  // Hard guarantee: if still under 4, recycle items from candidate pool so slots never show blank white
  if (moreDrinks.length < 4 && dedupedAll.length > 0) {
    const recycle = dedupedAll.filter(i => !moreDrinks.some(m => (m.id || m.name) === (i.id || i.name)));
    moreDrinks = [...moreDrinks, ...recycle, ...dedupedAll].slice(0, 4);
  }

  const handleFilterChange = useCallback((filter) => {
    const normalizedFilter = filter.trim().toLowerCase();
    setSelectedType(normalizedFilter);
  }, []);

  useEffect(() => {
    const handleVoiceUIAction = (event) => {
      const action = event.detail?.action;
      if (action === "filter_cold") {
        handleFilterChange("cold");
      } else if (action === "filter_hot") {
        handleFilterChange("hot");
      } else if (action === "filter_both") {
        handleFilterChange("both");
      } else if (action === "view_more") {
        navigate("/drinkmenu");
      } else if (action === "go_back") {
        navigate(-1);
      }
    };

    window.addEventListener("kiosk-ui-action", handleVoiceUIAction);
    return () => window.removeEventListener("kiosk-ui-action", handleVoiceUIAction);
  }, [handleFilterChange, navigate]);

  return (
    <div className="drink-page">
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
      <Header title="Choose Your Drink" />

      <BackButton />

      {/* FILTERS */}
      <div className="drink-filter-position">
        <Menufilters
          filters={[
            "both",
            "cold",
            "hot"
          ]}
          activeFilter={selectedType}
          onFilterChange={handleFilterChange}
        />
      </div>

      {/* PRIORITY */}
      {freshDrinks[0] && (
        <ProductCard
          product={freshDrinks[0]}
          variant="large"
          className="card-1"
          badge="popular"
        />
      )}

      {freshDrinks[1] && (
        <ProductCard
          product={freshDrinks[1]}
          variant="large"
          className="card-2"
          badge="popular"
        />
      )}

      {/* PREMIUM */}
      {premiumDrinks[0] && (
        <ProductCard
          product={premiumDrinks[0]}
          variant="large"
          className="card-3"
          badge="premium"
        />
      )}

      {premiumDrinks[1] && (
        <ProductCard
          product={premiumDrinks[1]}
          variant="large"
          className="card-4"
          badge="premium"
        />
      )}

      {/* ADDITIONAL */}
      {moreDrinks[0] && (
        <ProductCard
          product={moreDrinks[0]}
          variant="small"
          className="card-5"
        />
      )}

      {moreDrinks[1] && (
        <ProductCard
          product={moreDrinks[1]}
          variant="small"
          className="card-6"
        />
      )}

      {moreDrinks[2] && (
        <ProductCard
          product={moreDrinks[2]}
          variant="small"
          className="card-7"
        />
      )}

      {moreDrinks[3] && (
        <ProductCard
          product={moreDrinks[3]}
          variant="small"
          className="card-8"
        />
      )}

      {/* TITLES */}
      <p className="fresh-text">
        Freshly Made Drinks
      </p>

      <p className="fresh-text2">
        Popular & perfect right now
      </p>

      <p className="premium-text">
        Premium Beverages
      </p>

      <p className="premium-text2">
        Indulge in our most loved shakes & drinks
      </p>

      {/* MORE OPTIONS */}
      <div className="more-header">
        <p className="more-text">
          More Drink Options
        </p>

        <button
          className="view-all-btn"
          onClick={() => navigate("/drinkmenu")}
        >
          View All Drinks →
        </button>
      </div>

      {/* CART */}
      <CartContainer />

      {/* FOOTER */}
      <FooterDecoration />
    </div>
  );
}

export default Drink;