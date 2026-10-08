import "./Drinkrepage.css";

import { useNavigate } from "react-router-dom";

import {
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";
import Menufilters from "../components/Menufilters";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";

import { syncScreen } from "../services/screenService";

function Drink() {
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

  const [
    selectedType,
    setSelectedType
  ] = useState("both");

  const [menuItems, setMenuItems] = useState([]);

  // Fetch full category menu once for candidate pool backup
  useEffect(() => {
    let cancelled = false;
    fetch("/menu/drinks")
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

    fetch("/category/drink/recommendations")
      .then((res) => res.json())
      .then((resData) => {
        if (!cancelled && resData?.success && resData?.data) {
          setFallbackData(resData.data);
          if (setRecommendationData) {
            setRecommendationData({ data: resData.data });
          }
        }
      })
      .catch((err) => console.warn("Failed to fetch drink recommendations:", err));

    return () => {
      cancelled = true;
    };
  }, [cart, selectedType]);

  // ==========================================
  // MASTER BACKEND DATASET
  // ==========================================

  const data =
    recommendationData?.data ||
    fallbackData ||
    {};

  // ==========================================
  // REAL-TIME CART EXCLUSION FILTER (M7)
  // Ensures items in cart NEVER display in 4 cards or additional rows
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

  const matchesType = useCallback((item) => {
    if (!item) return false;
    if (selectedType === "both") return true;
    const type = String(item.type || "").toLowerCase().trim();
    return type === selectedType;
  }, [selectedType]);

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
        if (matchesType(item)) {
          deduped.push(item);
        }
      }
    }
    return deduped;
  }, [data, menuItems, matchesType]);

  // Dynamic backfill guaranteeing exactly 2 Priority and 2 Premium cards
  const { freshDrinks, premiumDrinks, moreDrinks } = useMemo(() => {
    const usedKeys = new Set();

    // 1. Priority Items (Cards 1 & 2)
    const priority = [];
    for (const item of (data.priority || [])) {
      if (notInCart(item) && matchesType(item)) {
        const key = item.id || item.name;
        priority.push(item);
        usedKeys.add(key);
        if (priority.length === 2) break;
      }
    }

    if (priority.length < 2) {
      for (const item of (data.additional || [])) {
        if (notInCart(item) && matchesType(item)) {
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
      if (notInCart(item) && matchesType(item)) {
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
      if (notInCart(item) && matchesType(item)) {
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
      freshDrinks: priority,
      premiumDrinks: premium,
      moreDrinks: additional,
    };
  }, [data, allCandidatesPool, notInCart, matchesType]);

  // ==========================================
  // SCREEN SYNC
  // ==========================================

  useEffect(() => {

    syncScreen(
      "recommended_drinks"
    );

  }, []);

  // ==========================================
  // FILTER CHANGES
  // ==========================================

  const handleFilterChange =
    useCallback((filter) => {

      const normalizedFilter =
        filter
          .trim()
          .toLowerCase()
          .replace("_", " ");

      console.log(
        "CHANGING DRINK FILTER:",
        normalizedFilter
      );

      setSelectedType(
        normalizedFilter
      );

    }, []);

  // ==========================================
  // VOICE UI ACTION LISTENER
  // ==========================================

  useEffect(() => {

    const handleVoiceUIAction =
      (event) => {

        const action =
          event.detail?.action;

        console.log(
          "DRINK PAGE RECEIVED UI ACTION:",
          action
        );

        if (
          action === "filter_cold"
        ) {

          handleFilterChange(
            "cold"
          );

        }

        else if (
          action === "filter_hot"
        ) {

          handleFilterChange(
            "hot"
          );

        }

        else if (
          action === "filter_both"
        ) {

          handleFilterChange(
            "both"
          );

        }

        else if (
          action === "view_more"
        ) {

          navigate(
            "/drinkmenu"
          );

        }

        else if (
          action === "go_back"
        ) {

          navigate(-1);

        }

      };

    window.addEventListener(
      "kiosk-ui-action",
      handleVoiceUIAction
    );

    return () => {

      window.removeEventListener(
        "kiosk-ui-action",
        handleVoiceUIAction
      );

    };

  }, [
    handleFilterChange,
    navigate
  ]);

  return (

    <div className="drink-page">

      {/* ===================================== */}
      {/* SECTION ICONS */}
      {/* ===================================== */}

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

      {/* ===================================== */}
      {/* HEADER */}
      {/* ===================================== */}

      <Header
        title="Choose Your Drink"
      />

      <BackButton />

      {/* ===================================== */}
      {/* FILTERS */}
      {/* ===================================== */}

      <div className="drink-filter-position">

        <Menufilters
          filters={[
            "both",
            "cold",
            "hot"
          ]}
          activeFilter={
            selectedType
          }
          onFilterChange={
            handleFilterChange
          }
        />

      </div>

      {/* ===================================== */}
      {/* PRIORITY */}
      {/* ===================================== */}

      {freshDrinks[0] && (

        <ProductCard
          product={
            freshDrinks[0]
          }
          variant="large"
          className="card-1"
          badge="popular"
        />

      )}

      {freshDrinks[1] && (

        <ProductCard
          product={
            freshDrinks[1]
          }
          variant="large"
          className="card-2"
          badge="popular"
        />

      )}

      {/* ===================================== */}
      {/* PREMIUM */}
      {/* ===================================== */}

      {premiumDrinks[0] && (

        <ProductCard
          product={
            premiumDrinks[0]
          }
          variant="large"
          className="card-3"
          badge="premium"
        />

      )}

      {premiumDrinks[1] && (

        <ProductCard
          product={
            premiumDrinks[1]
          }
          variant="large"
          className="card-4"
          badge="premium"
        />

      )}

      {/* ===================================== */}
      {/* ADDITIONAL */}
      {/* ===================================== */}

      {moreDrinks[0] && (

        <ProductCard
          product={
            moreDrinks[0]
          }
          variant="small"
          className="card-5"
        />

      )}

      {moreDrinks[1] && (

        <ProductCard
          product={
            moreDrinks[1]
          }
          variant="small"
          className="card-6"
        />

      )}

      {moreDrinks[2] && (

        <ProductCard
          product={
            moreDrinks[2]
          }
          variant="small"
          className="card-7"
        />

      )}

      {moreDrinks[3] && (

        <ProductCard
          product={
            moreDrinks[3]
          }
          variant="small"
          className="card-8"
        />

      )}

      {/* ===================================== */}
      {/* TITLES */}
      {/* ===================================== */}

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

      {/* ===================================== */}
      {/* MORE OPTIONS */}
      {/* ===================================== */}

      <div className="more-header">

        <p className="more-text">
          More Drink Options
        </p>

        <button
          className="view-all-btn"
          onClick={() =>
            navigate(
              "/drinkmenu"
            )
          }
        >
          View All Drinks →
        </button>

      </div>

      {/* ===================================== */}
      {/* CART */}
      {/* ===================================== */}

      <CartContainer />

      {/* ===================================== */}
      {/* FOOTER */}
      {/* ===================================== */}

      <FooterDecoration />

    </div>
  );
}

export default Drink;