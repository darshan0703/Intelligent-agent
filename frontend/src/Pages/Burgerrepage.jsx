import "./Burgerrepage.css";

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

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";

import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";
import FooterDecoration from "../components/FooterDecoration";

import { useKiosk } from "../context/KioskContext";
import { useCart } from "../context/CartContext";


function Burger() {

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
  // NORMALIZE FOOD PREFERENCE
  // ==========================================

  const normalizePreference = useCallback(
    (value) => {

      return String(value || "both")
        .toLowerCase()
        .replace(/_/g, " ")
        .trim();

    },
    []
  );


  // ==========================================
  // KEEP LOCAL FILTER IN SYNC
  // WITH GLOBAL FOOD PREFERENCE
  // ==========================================

  useEffect(() => {

    if (foodPreference) {

      setSelectedType(
        normalizePreference(foodPreference)
      );

    }

  }, [
    foodPreference,
    normalizePreference
  ]);


  // ==========================================
  // FALLBACK
  //
  // Only used when the page is opened directly
  // without recommendation data.
  // ==========================================

  const [menuItems, setMenuItems] = useState([]);

  // Fetch full category menu once for candidate pool backup
  useEffect(() => {
    let cancelled = false;
    fetch("/menu/burgers")
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

  // Primary recommendations fetch
  useEffect(() => {
    let cancelled = false;

    fetch("/category/burger/recommendations")
      .then((res) => res.json())
      .then((resData) => {
        if (!cancelled && resData?.success && resData?.data) {
          setFallbackData(resData.data);
          if (setRecommendationData) {
            setRecommendationData({ data: resData.data });
          }
        } else {
          throw new Error("Invalid recommendation data");
        }
      })
      .catch((error) => {
        if (cancelled) return;
        console.warn(
          "Primary burger recs fetch failed, using menu fallback:",
          error
        );
        fetch("/menu/burgers")
          .then((res) => res.json())
          .then((sections) => {
            if (cancelled) return;
            const all = sections.flatMap((s) => s.products || []);
            const veg = all.filter(
              (p) => String(p.type || p.foodType || "").toLowerCase().trim() === "veg"
            );
            const nonVeg = all.filter(
              (p) => String(p.type || p.foodType || "").toLowerCase().trim() === "non veg"
            );
            const byPriceDesc = [...all].sort((a, b) => (Number(b.price) || 0) - (Number(a.price) || 0));
            const premiumAll = byPriceDesc.filter((p) => (Number(p.price) || 0) >= 120).slice(0, 2);
            const premiumVeg = [...veg].sort((a, b) => (Number(b.price) || 0) - (Number(a.price) || 0)).filter((p) => (Number(p.price) || 0) >= 120).slice(0, 2);
            const premiumNonVeg = [...nonVeg].sort((a, b) => (Number(b.price) || 0) - (Number(a.price) || 0)).filter((p) => (Number(p.price) || 0) >= 120).slice(0, 2);

            const premIds = new Set(premiumAll.map((p) => p.id || p.name));
            const remainingAll = all.filter((p) => !premIds.has(p.id || p.name));

            setFallbackData({
              both: {
                priority: remainingAll.slice(0, 2),
                premium: premiumAll,
                additional: remainingAll.slice(2, 6),
              },
              veg: {
                priority: veg.filter((p) => !premiumVeg.some((pv) => pv.id === p.id)).slice(0, 2),
                premium: premiumVeg,
                additional: veg.filter((p) => !premiumVeg.some((pv) => pv.id === p.id)).slice(2, 6),
              },
              non_veg: {
                priority: nonVeg.filter((p) => !premiumNonVeg.some((pv) => pv.id === p.id)).slice(0, 2),
                premium: premiumNonVeg,
                additional: nonVeg.filter((p) => !premiumNonVeg.some((pv) => pv.id === p.id)).slice(2, 6),
              },
            });
          })
          .catch((err) => console.warn("Fallback burger fetch failed:", err));
      });

    return () => {
      cancelled = true;
    };
  }, [cart, selectedType]);


  // ==========================================
  // MASTER BACKEND RESPONSE
  // ==========================================

  const backendData =
    recommendationData?.data ||
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
    backendData[preferenceKey] ||
    backendData.both ||
    fallbackData?.[preferenceKey] ||
    fallbackData?.both ||
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
      ...(backendData.both?.priority || []),
      ...(backendData.both?.premium || []),
      ...(backendData.both?.additional || []),
      ...(backendData.veg?.priority || []),
      ...(backendData.veg?.premium || []),
      ...(backendData.veg?.additional || []),
      ...(backendData.non_veg?.priority || []),
      ...(backendData.non_veg?.premium || []),
      ...(backendData.non_veg?.additional || []),
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
  }, [selectedData, backendData, menuItems, selectedType]);

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

    // Backfill priority if fewer than 2 items remain
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

    // Backfill premium if fewer than 2 items remain
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
  // DEBUG
  // ==========================================

  console.log(
    "=========================================="
  );

  console.log(
    "BURGER SELECTED TYPE:",
    selectedType
  );

  console.log(
    "BURGER DATASET KEY:",
    preferenceKey
  );

  console.log(
    "BURGER SELECTED DATA:",
    selectedData
  );

  console.log(
    "BURGER PRIORITY:",
    priorityItems
  );

  console.log(
    "BURGER PREMIUM:",
    premiumItems
  );

  console.log(
    "BURGER ADDITIONAL:",
    additionalItems
  );

  console.log(
    "=========================================="
  );


  // ==========================================
  // SCREEN SYNC
  // ==========================================

  useEffect(() => {

    syncScreen(
      "recommended_burgers"
    );

  }, []);


  // ==========================================
  // FILTER CHANGE
  // ==========================================

  const handleFilterChange = useCallback(
    (filter) => {

      const normalizedFilter =
        normalizePreference(filter);


      console.log(
        "CHANGING BURGER FILTER:",
        normalizedFilter
      );


      setSelectedType(
        normalizedFilter
      );


      // Keep global preference synchronized.
      if (setFoodPreference) {

        setFoodPreference(
          normalizedFilter
        );

      }

    },
    [
      normalizePreference,
      setFoodPreference
    ]
  );


  // ==========================================
  // VOICE UI ACTION LISTENER
  // ==========================================

  useEffect(() => {

    const handleVoiceUIAction =
      (event) => {

        const action =
          event.detail?.action;


        console.log(
          "BURGER PAGE RECEIVED UI ACTION:",
          action
        );


        if (
          action === "filter_veg"
        ) {

          handleFilterChange(
            "veg"
          );

        }

        else if (
          action === "filter_non_veg"
        ) {

          handleFilterChange(
            "non veg"
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
            "/burgermenu"
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

    <div className="burger-page">

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
        title="Choose Your Burger"
      />


      <BackButton />


      {/* FILTERS */}

      <div className="burger-filter-position">

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


      {/* ==================================
          PRIORITY
          ================================== */}

      {
        priorityItems[0] && (

          <ProductCard
            product={
              priorityItems[0]
            }
            variant="large"
            className="card-1"
            badge="popular"
          />

        )
      }


      {
        priorityItems[1] && (

          <ProductCard
            product={
              priorityItems[1]
            }
            variant="large"
            className="card-2"
            badge="popular"
          />

        )
      }


      {/* ==================================
          PREMIUM
          ================================== */}

      {
        premiumItems[0] && (

          <ProductCard
            product={
              premiumItems[0]
            }
            variant="large"
            className="card-3"
            badge="premium"
          />

        )
      }


      {
        premiumItems[1] && (

          <ProductCard
            product={
              premiumItems[1]
            }
            variant="large"
            className="card-4"
            badge="premium"
          />

        )
      }


      {/* ==================================
          ADDITIONAL
          ================================== */}

      {
        additionalItems[0] && (

          <ProductCard
            product={
              additionalItems[0]
            }
            variant="small"
            className="card-5"
          />

        )
      }


      {
        additionalItems[1] && (

          <ProductCard
            product={
              additionalItems[1]
            }
            variant="small"
            className="card-6"
          />

        )
      }


      {
        additionalItems[2] && (

          <ProductCard
            product={
              additionalItems[2]
            }
            variant="small"
            className="card-7"
          />

        )
      }


      {
        additionalItems[3] && (

          <ProductCard
            product={
              additionalItems[3]
            }
            variant="small"
            className="card-8"
          />

        )
      }


      {/* ==================================
          RECOMMENDED SECTION
          ================================== */}

      <p className="Recommendation-text">
        Fresh Picks For You
      </p>

      <p className="Recommendation-text2">
        Recommended based on availability
      </p>


      {/* ==================================
          PREMIUM SECTION
          ================================== */}

      {premiumItems.length > 0 && (
        <>
          <p className="Premium-text">
            Premium Collection
          </p>

          <p className="Premium-text2">
            Handpicked just for you
          </p>
        </>
      )}


      {/* ==================================
          MORE OPTIONS
          ================================== */}

      <div className="more-header">

        <p className="more-text">
          More Burger Options
        </p>


        <button
          className="view-all-btn"
          onClick={() =>
            navigate(
              "/burgermenu",
              {
                state: {
                  activeFilter:
                    selectedType,
                },
              }
            )
          }
        >
          View All Burgers →
        </button>

      </div>


      {/* CART */}

      <CartContainer />


      {/* FOOTER */}

      <FooterDecoration />

    </div>

  );

}


export default Burger;