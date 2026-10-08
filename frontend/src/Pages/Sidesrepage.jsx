import "./Sidesrepage.css";

import { useNavigate } from "react-router-dom";

import {
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";

import { syncScreen } from "../services/screenService";

import Menufilters from "../components/Menufilters";

import Header from "../components/Header";

import ProductCard from "../components/ProductCard";

import CartContainer from "../components/CartContainer";

import BackButton from "../components/BackButton";

import FooterDecoration from "../components/FooterDecoration";

import fire from "../assets/images/fire.png";

import crown from "../assets/images/crown.png";

import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";

import { sendMessage } from "../services/api";


function Sides() {

  const navigate = useNavigate();


  const {
    recommendationData,
    setRecommendationData,
    foodPreference,
    setFoodPreference,
  } = useKiosk();

  const { cart } = useCart();


  const [
    selectedType,
    setSelectedType
  ] = useState(
    foodPreference || "both"
  );


  const [
    fallbackData,
    setFallbackData
  ] = useState(null);


  // ==========================================
  // KEEP LOCAL FILTER IN SYNC
  // WITH GLOBAL FOOD PREFERENCE
  // ==========================================

  useEffect(() => {

    if (foodPreference) {

      setSelectedType(foodPreference);

    }

  }, [foodPreference]);


  // ==========================================
  // FALLBACK
  //
  // Restore recommendation data from backend
  // when page is opened directly or refreshed.
  //
  // IMPORTANT:
  //
  // The frontend does NOT create
  // recommendation tiers here.
  //
  // The backend remains responsible for:
  //
  // - priority
  // - premium
  // - additional
  // - veg
  // - non veg
  // ==========================================

  const [menuItems, setMenuItems] = useState([]);

  // Fetch full category menu once for candidate pool backup
  useEffect(() => {
    let cancelled = false;
    fetch("/menu/sides")
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

    fetch("/category/side/recommendations")
      .then((res) => res.json())
      .then((resData) => {
        if (!cancelled && resData?.success && resData?.data) {
          setFallbackData(resData.data);
          if (setRecommendationData) {
            setRecommendationData({ data: resData.data });
          }
        }
      })
      .catch((error) => {
        if (!cancelled) {
          console.warn("Direct side recs fetch failed, using sendMessage fallback:", error);
          sendMessage("I want some sides")
            .then((data) => {
              if (!cancelled && data) {
                setFallbackData(data);
              }
            })
            .catch((err) => console.error("Failed to restore side recommendations:", err));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [cart, selectedType]);


  // ==========================================
  // MASTER BACKEND RESPONSE
  // ==========================================

  const data =
    recommendationData?.data ||
    fallbackData?.data ||
    fallbackData ||
    {};


  // ==========================================
  // SELECT BACKEND DATASET
  // ==========================================

  const preferenceKey =
    selectedType === "veg"
      ? "veg"
      : selectedType === "non veg"
        ? "non_veg"
        : "both";


  const selectedData =
    data[preferenceKey] ||
    data.both ||
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

  // Complete pool of eligible candidates for zero-white-card replenishment
  const allCandidatesPool = useMemo(() => {
    const list = [
      ...(selectedData.priority || []),
      ...(selectedData.premium || []),
      ...(selectedData.additional || []),
      ...(data.both?.priority || []),
      ...(data.both?.premium || []),
      ...(data.both?.additional || []),
      ...(data.veg?.priority || []),
      ...(data.veg?.premium || []),
      ...(data.veg?.additional || []),
      ...(data.non_veg?.priority || []),
      ...(data.non_veg?.premium || []),
      ...(data.non_veg?.additional || []),
      ...menuItems,
    ];
    const seen = new Set();
    const deduped = [];
    for (const item of list) {
      if (!item) continue;
      const key = item.id || item.name;
      if (!seen.has(key)) {
        seen.add(key);
        const itemType = String(item.type || item.foodType || "").toLowerCase().trim();
        if (selectedType === "veg" && itemType && !itemType.includes("veg")) continue;
        if (selectedType === "veg" && itemType.includes("non")) continue;
        if (selectedType === "non veg" && itemType && !itemType.includes("non")) continue;
        deduped.push(item);
      }
    }
    return deduped;
  }, [selectedData, data, menuItems, selectedType]);

  // Dynamic backfill guaranteeing exactly 2 Priority and 2 Premium cards
  const { priorityItems, premiumItems, additionalItems } = useMemo(() => {
    const usedKeys = new Set();

    // 1. Priority Items (Cards 1 & 2)
    const priority = [];
    for (const item of (selectedData.priority || [])) {
      if (notInCart(item)) {
        const key = item.id || item.name;
        priority.push(item);
        usedKeys.add(key);
        if (priority.length === 2) break;
      }
    }

    if (priority.length < 2) {
      for (const item of (selectedData.additional || [])) {
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
    for (const item of (selectedData.premium || [])) {
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
    for (const item of (selectedData.additional || [])) {
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
      priorityItems: priority,
      premiumItems: premium,
      additionalItems: additional,
    };
  }, [selectedData, allCandidatesPool, notInCart]);


  // ==========================================
  // SCREEN SYNC
  // ==========================================

  useEffect(() => {

    syncScreen("recommended_sides");

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
          .replace(/_/g, " ");


      console.log(
        "CHANGING SIDES FILTER:",
        normalizedFilter
      );


      setSelectedType(
        normalizedFilter
      );


      if (setFoodPreference) {

        setFoodPreference(
          normalizedFilter
        );

      }

    }, [
      setFoodPreference
    ]);


  // ==========================================
  // VOICE UI ACTION LISTENER
  // ==========================================

  useEffect(() => {

    const handleVoiceUIAction = (event) => {

      const action =
        event.detail?.action;


      console.log(
        "SIDES PAGE RECEIVED UI ACTION:",
        action
      );


      if (
        action === "filter_veg"
      ) {

        handleFilterChange("veg");

      } else if (
        action === "filter_non_veg"
      ) {

        handleFilterChange("non veg");

      } else if (
        action === "filter_both"
      ) {

        handleFilterChange("both");

      } else if (
        action === "view_more"
      ) {

        navigate("/sidesmenu");

      } else if (
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

    <div className="sides-page">

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

      <Header
        title="Choose Your Sides"
      />


      <BackButton />


      {/* FILTERS */}

      <div className="sides-filter-position">

        <Menufilters

          filters={[
            "both",
            "veg",
            "non veg",
          ]}

          activeFilter={
            selectedType
          }

          onFilterChange={
            handleFilterChange
          }

        />

      </div>


      {/* PRIORITY */}

      {priorityItems[0] && (

        <ProductCard

          product={
            priorityItems[0]
          }

          variant="large"

          className="card-1"

          badge="popular"

        />

      )}


      {priorityItems[1] && (

        <ProductCard

          product={
            priorityItems[1]
          }

          variant="large"

          className="card-2"

          badge="popular"

        />

      )}


      {/* PREMIUM */}

      {premiumItems[0] && (

        <ProductCard

          product={
            premiumItems[0]
          }

          variant="large"

          className="card-3"

          badge="premium"

        />

      )}


      {premiumItems[1] && (

        <ProductCard

          product={
            premiumItems[1]
          }

          variant="large"

          className="card-4"

          badge="premium"

        />

      )}


      {/* ADDITIONAL */}

      {additionalItems[0] && (

        <ProductCard

          product={
            additionalItems[0]
          }

          variant="small"

          className="card-5"

        />

      )}


      {additionalItems[1] && (

        <ProductCard

          product={
            additionalItems[1]
          }

          variant="small"

          className="card-6"

        />

      )}


      {additionalItems[2] && (

        <ProductCard

          product={
            additionalItems[2]
          }

          variant="small"

          className="card-7"

        />

      )}


      {additionalItems[3] && (

        <ProductCard

          product={
            additionalItems[3]
          }

          variant="small"

          className="card-8"

        />

      )}


      {/* TITLES */}

      <p className="fresh-text">

        Hot & Crispy Picks

      </p>


      <p className="fresh-text2">

        Freshly prepared favorites

      </p>


      <p className="premium-text">

        Premium Sides

      </p>


      <p className="premium-text2">

        Perfect add-ons for every meal

      </p>


      {/* MORE OPTIONS */}

      <div className="more-header">

        <p className="more-text">

          More Side Options

        </p>


        <button

          className="view-all-btn"

          onClick={() =>
            navigate(
              "/sidesmenu",
              {
                state: {
                  activeFilter:
                    selectedType,
                },
              }
            )
          }

        >

          View All Sides →

        </button>

      </div>


      {/* CART */}

      <CartContainer />


      {/* FOOTER */}

      <FooterDecoration />

    </div>

  );

}


export default Sides;