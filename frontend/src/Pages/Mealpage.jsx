import "./Mealpage.css";
import React, { useState, useMemo, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";
import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";
import FooterDecoration from "../components/FooterDecoration";
import { syncScreen } from "../services/screenService";
import { createPerfTracker, measureScreenRender } from "../services/perf";

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

function MealPage({ meal: propMeal } = {}) {
    const { state } = useLocation();
    const navigate = useNavigate();
    const rawOrigin = state?.origin;
    const origin = (rawOrigin && rawOrigin !== "/") ? rawOrigin : "/burgers";
    const [meal, setMeal] = useState(propMeal || state?.meal);

    useEffect(() => {
        const nextMeal = propMeal || state?.meal;
        if (nextMeal) {
            setMeal(nextMeal);
        }
    }, [propMeal, state?.meal]);

    const burger = meal?.burger;
    const side = meal?.side;
    const drink = meal?.drink;

    const { syncCart, cart, notifyCartItemAdded } = useCart();
    const { foodPreference } = useKiosk();
    const mealSize = meal?.size || "Medium";
    const [quantity, setQuantity] = useState(1);

    const [selectedSide, setSelectedSide] = useState(side);

    const burgerFoodType = String(burger?.foodType || burger?.food_type || "").toLowerCase().trim();
    const userPref = String(foodPreference || "").toLowerCase().trim();

    // Context-aware preference:
    // If user explicitly chose 'veg' or 'non_veg', respect that.
    // If user is in 'both' / neutral, infer from the burger itself!
    // A Veg Burger builds a Veg meal (all Veg sides first), Non-Veg burger builds Non-Veg first.
    const effectivePref = useMemo(() => {
        if (userPref === "veg") return "veg";
        if (userPref.includes("non")) return "non_veg";
        return burgerFoodType === "veg" ? "veg" : "non_veg";
    }, [userPref, burgerFoodType]);

    const isVegItem = (item) => {
        const ft = String(item?.foodType || item?.food_type || "")
            .toLowerCase()
            .replace("-", "_")
            .replace(" ", "_")
            .trim();
        return ft === "veg";
    };

    const isItemInCart = (item) => {
        if (!item || !cart || !Array.isArray(cart)) return false;
        const itemId = item.id;
        const itemName = String(item.name || "").trim().toLowerCase();
        return cart.some((c) => {
            if (c.id && itemId && String(c.id) === String(itemId)) return true;
            const cName = String(c.name || "").trim().toLowerCase();
            if (cName && (cName === itemName || (itemName.length > 5 && cName === itemName))) return true;

            // Check inside meal combo in cart
            if (c.type === "meal") {
                const main = c.main_item || c.burger || {};
                const s = c.side || {};
                const d = c.drink || {};
                if (String(main.id) === String(itemId) || String(s.id) === String(itemId) || String(d.id) === String(itemId)) return true;
                if (main.name && String(main.name).trim().toLowerCase() === itemName) return true;
                if (s.name && String(s.name).trim().toLowerCase() === itemName) return true;
                if (d.name && String(d.name).trim().toLowerCase() === itemName) return true;
            }
            return false;
        });
    };

    const sideOptions = meal?.side_options ?? [];

    const drinkSections = useMemo(() => [
        ...new Set(
            (meal?.drink_options ?? []).map(
                item => item.section
            ).filter(Boolean)
        )
    ], [meal?.drink_options]);

    const defaultDrinkSection =
        (meal?.drink_options ?? []).find(d => String(d.id) === String(drink?.id))?.section ||
        drink?.section ||
        drinkSections[0] ||
        "";

    const [selectedDrinkSection, setSelectedDrinkSection] =
        useState(defaultDrinkSection);

    const [selectedDrink, setSelectedDrink] =
        useState(drink);

    const visibleDrinks = useMemo(() => {
        const options = meal?.drink_options ?? [];
        if (!selectedDrinkSection) return options;
        return options.filter(
            item => item.section === selectedDrinkSection
        );
    }, [meal?.drink_options, selectedDrinkSection]);

    const mealKey = meal
        ? `${meal.burger?.id || meal.id || ""}_${meal.size || ""}_${meal.side?.id || ""}_${meal.drink?.id || ""}`
        : null;
    const initializedMealKeyRef = useRef(null);
    const userSelectedSideRef = useRef(false);
    const userSelectedDrinkRef = useRef(false);
    const userSelectedSectionRef = useRef(false);
    const isNavigatingRef = useRef(false);

    // Sequence tracking refs to eliminate touch-voice race conditions
    const lastSideTouchSeqRef = useRef(0);
    const lastDrinkTouchSeqRef = useRef(0);
    const selectedSideRef = useRef(selectedSide);
    const selectedDrinkRef = useRef(selectedDrink);
    selectedSideRef.current = selectedSide;
    selectedDrinkRef.current = selectedDrink;

    useEffect(() => {
        isNavigatingRef.current = false;
    }, [burger?.id, meal?.id]);

    const triggerMealSync = (sideItem, drinkItem) => {
        const sessionId =
            (typeof localStorage !== "undefined" &&
                localStorage.getItem("session_id")) ||
            "default";
        return syncScreen("meal_conversion", {
            session_id: sessionId,
            meal_customization: {
                meal_id: meal?.id,
                burger: burger,
                size: mealSize,
                selected_side: sideItem,
                selected_drink: drinkItem,
                side_options: meal?.side_options || [],
                drink_options: meal?.drink_options || [],
                meal_price: meal?.meal_price || 0,
            },
        });
    };

    const handleSideSelect = (item) => {
        userSelectedSideRef.current = true;
        setSelectedSide(item);
        selectedSideRef.current = item;
        const syncRes = triggerMealSync(item, selectedDrinkRef.current);
        if (syncRes && syncRes.seq) {
            lastSideTouchSeqRef.current = syncRes.seq;
        }
    };

    const handleDrinkSelect = (item) => {
        userSelectedDrinkRef.current = true;
        setSelectedDrink(item);
        selectedDrinkRef.current = item;
        const syncRes = triggerMealSync(selectedSideRef.current, item);
        if (syncRes && syncRes.seq) {
            lastDrinkTouchSeqRef.current = syncRes.seq;
        }
    };

    useEffect(() => {
        if (!meal) return;

        const isNewMeal = mealKey && mealKey !== initializedMealKeyRef.current;
        if (isNewMeal) {
            initializedMealKeyRef.current = mealKey;

            // Only initialize side strictly from included default side if user has NOT chosen one
            if (!userSelectedSideRef.current) {
                const initialSide = meal.side ? meal.side : null;
                setSelectedSide(initialSide);
                selectedSideRef.current = initialSide;
            }

            // Only initialize drink strictly from included default drink if user has NOT chosen one
            if (!userSelectedDrinkRef.current) {
                const initialDrink = meal.drink ? meal.drink : null;
                setSelectedDrink(initialDrink);
                selectedDrinkRef.current = initialDrink;
            }

            // Initialize drink category to default drink's category if user has not changed section
            if (!userSelectedSectionRef.current) {
                const initialSection =
                    (meal.drink_options ?? []).find((d) => String(d.id) === String(meal.drink?.id))?.section ||
                    meal.drink?.section ||
                    (meal.drink_options && meal.drink_options[0]?.section) ||
                    "";
                if (initialSection) {
                    setSelectedDrinkSection(initialSection);
                }
            }

            // Immediately synchronize initial meal state so voice observes current state
            const syncRes = triggerMealSync(selectedSideRef.current, selectedDrinkRef.current);
            if (syncRes && syncRes.seq) {
                lastSideTouchSeqRef.current = syncRes.seq;
                lastDrinkTouchSeqRef.current = syncRes.seq;
            }
        }
    }, [meal, mealKey]);

    const mealPrice =
        meal?.meal_price ?? 0;

    const sideExtra =
        selectedSide?.extra_price ?? 0;

    const drinkExtra =
        selectedDrink?.extra_price ?? 0;

    const totalPrice =
        mealPrice +
        sideExtra +
        drinkExtra;

    console.log("Burger:", burger);
    const handleAddMeal = async () => {
        if (isNavigatingRef.current) return;
        const sideToUse = selectedSideRef.current || selectedSide;
        const drinkToUse = selectedDrinkRef.current || selectedDrink;
        if (!sideToUse || !drinkToUse) {
            alert("Please select both a side and a drink to complete your meal.");
            return;
        }
        isNavigatingRef.current = true;

        const tracker = createPerfTracker("touch");
        tracker.log("touch_action_initiated", { action: "add_meal" });

        try {
            const endBackend = tracker.startStage("backend_request", { endpoint: "/cart/add-meal" });
            const response = await fetch(
                "/cart/add-meal",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "X-Interaction-ID": tracker.id,
                    },

                    body: JSON.stringify({
                        meal: {
                            ...meal,
                            side: sideToUse,
                            drink: drinkToUse
                        },
                        quantity
                    })

                }
            );

            const data = await response.json();
            endBackend();
            tracker.log("milestone_backend_response_received", {
                duration_ms: (performance.now() - tracker.startTime).toFixed(2),
                endpoint: "/cart/add-meal",
            });

            console.log("ADD MEAL:", data);

            if (data.success) {
                syncCart(data);
                notifyCartItemAdded();
                tracker.log("navigation_initiated", { destination: origin });
                navigate(origin);
                measureScreenRender(tracker, origin);
            }

        } catch (error) {

            console.error(error);

        }

    };
    const handleDeclineMeal = async () => {
        if (isNavigatingRef.current) return;
        isNavigatingRef.current = true;
        const tracker = createPerfTracker("touch");
        tracker.log("touch_action_initiated", { action: "decline_meal" });
        try {
            const endBackend = tracker.startStage("backend_request", { endpoint: "/meal/decline" });
            const response = await fetch(
                "/meal/decline",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Interaction-ID": tracker.id,
                    },
                    body: JSON.stringify({
                        item_id: burger?.id,
                        product_id: burger?.id,
                    }),
                }
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            endBackend();
            tracker.log("milestone_backend_response_received", {
                duration_ms: (performance.now() - tracker.startTime).toFixed(2),
                endpoint: "/meal/decline",
            });

            if (!data.success) {
                throw new Error(data.message || "Failed to record meal decline");
            }

            console.log("MEAL DECLINED:", data);

        } catch (error) {
            console.warn("Failed to decline meal on backend:", error);
        } finally {
            tracker.log("navigation_initiated", { destination: origin });
            navigate(origin);
            measureScreenRender(tracker, origin);
        }
    };

    // Voice UI Action Listener for meal swaps, add-to-cart, decline, and go-back
    useEffect(() => {
        const handleVoiceUIAction = (event) => {
            const { action, value } = event.detail || {};

            if (action === "select_meal" || action === "select_meal_large" || action === "select_meal_medium") {
                const targetSize = (action === "select_meal_large" ? "large" : action === "select_meal_medium" ? "medium" : (typeof value === "string" ? value : value?.size || "large")).toLowerCase();
                const newMeal = event.detail?.meal || (typeof value === "object" ? value?.meal : null);
                const currentSide = selectedSideRef.current;
                const currentDrink = selectedDrinkRef.current;
                const hadUserSide = userSelectedSideRef.current;
                const hadUserDrink = userSelectedDrinkRef.current;

                const applyUpgradedMeal = (upgradedMeal) => {
                    let sideToApply = upgradedMeal.side;
                    if (hadUserSide && currentSide) {
                        const matched = (upgradedMeal.side_options ?? []).find(
                            (s) =>
                                String(s.id) === String(currentSide.id) ||
                                String(s.name || "").toLowerCase() === String(currentSide.name || "").toLowerCase()
                        );
                        if (matched) sideToApply = matched;
                        else sideToApply = currentSide;
                    }

                    let drinkToApply = upgradedMeal.drink;
                    if (hadUserDrink && currentDrink) {
                        const matched = (upgradedMeal.drink_options ?? []).find(
                            (d) =>
                                String(d.id) === String(currentDrink.id) ||
                                String(d.name || "").toLowerCase() === String(currentDrink.name || "").toLowerCase()
                        );
                        if (matched) drinkToApply = matched;
                        else drinkToApply = currentDrink;
                    }

                    setSelectedSide(sideToApply);
                    selectedSideRef.current = sideToApply;
                    setSelectedDrink(drinkToApply);
                    selectedDrinkRef.current = drinkToApply;
                    setMeal(upgradedMeal);
                    triggerMealSync(sideToApply, drinkToApply);
                };

                if (newMeal) {
                    applyUpgradedMeal(newMeal);
                } else if (meal?.burger?.id) {
                    fetch("/meal/options", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ item_id: meal.burger.id }),
                    })
                    .then((r) => r.json())
                    .then((data) => {
                        if (data.success && data.meals?.[targetSize]) {
                            applyUpgradedMeal(data.meals[targetSize]);
                        }
                    })
                    .catch((err) => console.error("Error updating meal size on MealPage:", err));
                }
            } else if (action === "swap_meal_item") {
                const { role, item, seq, session_id } = value || {};
                const currentSessionId =
                    (typeof localStorage !== "undefined" &&
                        localStorage.getItem("session_id")) ||
                    "default";

                // Check session validity
                if (session_id && session_id !== currentSessionId) {
                    console.log("Ignored swap_meal_item from previous session:", session_id);
                    return;
                }

                if (role === "drink" && item) {
                    // Check against newer touch sequence for drink
                    if (seq && seq < lastDrinkTouchSeqRef.current) {
                        console.log("Ignored stale voice drink action:", seq, "vs", lastDrinkTouchSeqRef.current);
                        return;
                    }

                    const matchedDrink =
                        (meal?.drink_options ?? []).find(
                            (d) =>
                                String(d.id) === String(item.id) ||
                                String(d.name || "").toLowerCase() === String(item.name || "").toLowerCase()
                        ) || item;

                    setSelectedDrink(matchedDrink);
                    selectedDrinkRef.current = matchedDrink;

                    if (matchedDrink.section && matchedDrink.section !== selectedDrinkSection) {
                        setSelectedDrinkSection(matchedDrink.section);
                    }

                    const syncRes = triggerMealSync(selectedSideRef.current, matchedDrink);
                    if (syncRes && syncRes.seq) {
                        lastDrinkTouchSeqRef.current = syncRes.seq;
                    }
                } else if (role === "side" && item) {
                    // Check against newer touch sequence for side
                    if (seq && seq < lastSideTouchSeqRef.current) {
                        console.log("Ignored stale voice side action:", seq, "vs", lastSideTouchSeqRef.current);
                        return;
                    }

                    const matchedSide =
                        (meal?.side_options ?? []).find(
                            (s) =>
                                String(s.id) === String(item.id) ||
                                String(s.name || "").toLowerCase() === String(item.name || "").toLowerCase()
                        ) || item;

                    setSelectedSide(matchedSide);
                    selectedSideRef.current = matchedSide;

                    const syncRes = triggerMealSync(matchedSide, selectedDrinkRef.current);
                    if (syncRes && syncRes.seq) {
                        lastSideTouchSeqRef.current = syncRes.seq;
                    }
                }
            } else if (action === "add_to_cart") {
                if (isNavigatingRef.current) return;
                if (event.detail?.cart) {
                    isNavigatingRef.current = true;
                    syncCart(event.detail);
                    notifyCartItemAdded();
                    navigate(origin);
                } else {
                    handleAddMeal();
                }
            } else if (action === "decline_meal" || action === "go_back") {
                if (isNavigatingRef.current) return;
                isNavigatingRef.current = true;
                handleDeclineMeal();
            }
        };

        window.addEventListener("kiosk-ui-action", handleVoiceUIAction);
        return () => {
            window.removeEventListener("kiosk-ui-action", handleVoiceUIAction);
        };
    }, [meal, mealSize, burger, selectedDrinkSection]);
    return (

        <div className="meal-page">

            <Header title="Meal Builder" />

            <PreviousButton onClick={handleDeclineMeal} />

            {burger && (

                <>

                    {/* ================= HERO ================= */}

                    <div className="meal-top">

                        {/* LEFT PANEL */}

                        <div className="meal-left">

                            <div className="meal-title-area">

                                <h1 className="meal-name">

                                    {burger.name}

                                    {burger.foodType && (

                                        <img
                                            src={
                                                burger.foodType === "veg"
                                                    ? vegIcon
                                                    : nonVegIcon
                                            }
                                            alt=""
                                            className="meal-type-icon"
                                        />

                                    )}

                                </h1>
                            </div>

                            <div className="meal-description-area">

                                <p className="meal-short">

                                    {burger.shortDescription}

                                </p>

                            </div>

                            <div className="meal-badge-area">

                                <div className="meal-badge">

                                    🍔 {mealSize.toUpperCase()} MEAL

                                </div>

                            </div>

                            <div className="meal-summary-area">

                                <h3>

                                    Meal Includes

                                </h3>

                                <div className="meal-include-item">

                                    <div className="meal-item-left">

                                        🍟 {selectedSide?.name || "Select an available side"}

                                    </div>

                                    <div className="meal-item-right">

                                        {selectedSide ? (sideExtra > 0 ? `+₹${sideExtra}` : "₹0") : "—"}

                                    </div>

                                </div>

                                <div className="meal-include-item">

                                    <div className="meal-item-left">

                                        🥤 {selectedDrink?.name || "Select an available drink"}

                                    </div>

                                    <div className="meal-item-right">

                                        {selectedDrink ? (drinkExtra > 0 ? `+₹${drinkExtra}` : "₹0") : "—"}

                                    </div>

                                </div>

                                <div className="meal-price-divider"></div>

                                <div className="meal-price-row total">

                                    <div>

                                        Meal Price

                                    </div>

                                    <div>

                                        ₹{totalPrice}

                                    </div>

                                </div>

                            </div>

                        </div>

                        {/* RIGHT PANEL */}

                        <div className="meal-right">

                            <div className="meal-image-wrapper">

                                <img

                                    src={
                                        burger.meal_image ||
                                        burger.image
                                    }

                                    alt={burger.name}

                                    className="meal-product-image"

                                />

                            </div>


                        </div>

                    </div>

                    {/* ================= SCROLL AREA ================= */}

                    <div className="meal-content">

                        {/* ================= SIDE SELECTION ================= */}

                        <h2 className="meal-section">
                            1. Choose Your Side
                        </h2>

                        <div className="meal-grid">

                            {sideOptions.map((item) => (

                                <div

                                    key={item.id}

                                    className={`meal-card ${
                                        Boolean(
                                            selectedSide &&
                                            (String(selectedSide.id) === String(item.id) ||
                                             (selectedSide.name && item.name && selectedSide.name.toLowerCase() === item.name.toLowerCase()))
                                        ) ? "active" : ""
                                    }`}

                                    onClick={() => handleSideSelect(item)}

                                >

                                    <div className="meal-card-image">

                                        <img
                                            src={item.image}
                                            alt={item.name}
                                            className="meal-item-image"
                                        />

                                    </div>

                                    <div className="meal-card-name">

                                        <p style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px" }}>

                                            <img
                                                src={isVegItem(item) ? vegIcon : nonVegIcon}
                                                alt=""
                                                style={{ width: "13px", height: "13px", objectFit: "contain", flexShrink: 0 }}
                                            />

                                            {item.name}

                                        </p>

                                    </div>

                                    <div className="meal-card-price">

                                        {item.extra_price > 0 && (

                                            <span className="upgrade-price">

                                                +₹{item.extra_price}

                                            </span>

                                        )}

                                    </div>

                                </div>

                            ))}

                        </div>

                        {/* ================= DRINKS ================= */}

                        <h2 className="meal-section">
                            2. Choose Your Drink
                        </h2>

                        <div className="drink-filters">

                            {drinkSections.map((section) => (

                                <button

                                    key={section}

                                    className={
                                        selectedDrinkSection === section
                                            ? "active"
                                            : ""
                                    }

                                    onClick={() => {
                                        userSelectedSectionRef.current = true;
                                        setSelectedDrinkSection(section);
                                    }}

                                >

                                    {section}

                                </button>

                            ))}

                        </div>

                        <div className="drink-grid">

                            {visibleDrinks.map((item) => (

                                <div

                                    key={item.id}

                                    className={`drink-card ${
                                        Boolean(
                                            selectedDrink &&
                                            (String(selectedDrink.id) === String(item.id) ||
                                             (selectedDrink.name && item.name && selectedDrink.name.toLowerCase() === item.name.toLowerCase()))
                                        ) ? "active" : ""
                                    }`}

                                    onClick={() => handleDrinkSelect(item)}

                                >

                                    <div className="drink-card-image">

                                        <img

                                            src={item.image}

                                            alt={item.name}

                                            className="drink-item-image"

                                        />

                                    </div>

                                    <div className="drink-card-name">

                                        <p>

                                            {item.name}

                                        </p>

                                    </div>

                                    <div className="drink-card-price">

                                        {item.extra_price > 0 && (

                                            <span className="upgrade-price">

                                                +₹{item.extra_price}

                                            </span>

                                        )}

                                    </div>

                                </div>

                            ))}

                        </div>

                    </div>

                    <div className="meal-quantity-selector">

                        <button
                            className="qty-btn"
                            onClick={() =>
                                setQuantity(prev =>
                                    prev > 1 ? prev - 1 : 1
                                )
                            }
                        >
                            −
                        </button>

                        <span className="meal-qty-value">
                            {quantity}
                        </span>

                        <button
                            className="qty-btn"
                            onClick={() =>
                                setQuantity(prev => prev + 1)
                            }
                        >
                            +
                        </button>

                    </div>

                    <button
                        className="meal-add-cart-btn"
                        onClick={handleAddMeal}
                        disabled={!selectedSide || !selectedDrink}
                        style={(!selectedSide || !selectedDrink) ? { opacity: 0.6, cursor: "not-allowed" } : undefined}
                    >
                        {(!selectedSide || !selectedDrink)
                            ? "Choose Side & Drink to Add Meal"
                            : `Add Meal To Cart • ₹${totalPrice * quantity}`}
                    </button>

                </>

            )}

            <CartContainer />

            <FooterDecoration />

        </div>

    );

}

export default MealPage;