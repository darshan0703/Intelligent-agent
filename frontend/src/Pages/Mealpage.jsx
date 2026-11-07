import "./Mealpage.css";
import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";
import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";
import FooterDecoration from "../components/FooterDecoration";

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

function MealPage({ meal: propMeal } = {}) {
    const { state } = useLocation();
    const navigate = useNavigate();
    const origin = state?.origin || "/";

    // Cart and kiosk context
    const { syncCart, cart, notifyCartItemAdded } = useCart();
    const { foodPreference } = useKiosk();

    // Active meal data (chosen in previous popup: medium or large)
    const [meal, setMeal] = useState(() => propMeal || state?.meal || null);
    const [loading, setLoading] = useState(false);
    const [errorMsg, setErrorMsg] = useState(null);

    const mealSize = meal?.size || "Medium";
    const [quantity, setQuantity] = useState(1);
    const [selectedSide, setSelectedSide] = useState(null);
    const [selectedDrink, setSelectedDrink] = useState(null);
    const [selectedDrinkSection, setSelectedDrinkSection] = useState("");

    const userSelectedSideRef = useRef(false);
    const userSelectedDrinkRef = useRef(false);
    const userSelectedSectionRef = useRef(false);

    // 1. Resolve product ID for dynamic backend fetching on direct link/reload
    const resolvedProductId = useMemo(() => {
        if (meal?.burger?.id) return meal.burger.id;
        if (state?.productId) return state.productId;
        if (typeof window !== "undefined") {
            const params = new URLSearchParams(window.location.search);
            const queryId = params.get("product_id") || params.get("id");
            if (queryId) return queryId;
            return sessionStorage.getItem("current_meal_product_id");
        }
        return null;
    }, [meal?.burger?.id, state?.productId]);

    // Save product ID to sessionStorage
    useEffect(() => {
        if (resolvedProductId) {
            try {
                sessionStorage.setItem("current_meal_product_id", String(resolvedProductId));
            } catch (_) {}
        }
    }, [resolvedProductId]);

    // 2. Fetch live meal options dynamically from backend if page was refreshed
    const fetchMealData = useCallback(async (productId) => {
        if (!productId) return;
        setLoading(true);
        setErrorMsg(null);
        try {
            const response = await fetch("/meal/options", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    item_id: productId,
                    food_preference: foodPreference,
                    cart: cart || [],
                }),
            });
            const data = await response.json();
            if (data.success && data.is_meal_available && data.meals) {
                const targetSize = (meal?.size || "medium").toLowerCase();
                const targetMeal = data.meals[targetSize] || data.meals.medium || data.meals.large;
                if (targetMeal) {
                    setMeal(targetMeal);
                }
            } else {
                if (!meal) {
                    setErrorMsg(data.message || "Meal options are not available for this product.");
                }
            }
        } catch (err) {
            console.error("Failed to fetch dynamic meal options:", err);
            if (!meal) {
                setErrorMsg("Unable to connect to server. Please try again.");
            }
        } finally {
            setLoading(false);
        }
    }, [foodPreference, cart, meal]);

    // On mount: if meal is missing, fetch from backend
    useEffect(() => {
        if (!meal && resolvedProductId) {
            fetchMealData(resolvedProductId);
        }
    }, [meal, resolvedProductId, fetchMealData]);

    // Synchronize screen state with backend
    useEffect(() => {
        fetch("/screen", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ screen: "meal" }),
        }).catch((err) => console.warn("Screen sync error:", err));
    }, []);

    // 3. Dynamic Drink Sections Order (computed by backend based on time-of-day & burger price)
    const drinkSections = useMemo(() => {
        if (meal?.drink_sections && meal.drink_sections.length > 0) {
            return meal.drink_sections;
        }
        return [
            ...new Set(
                (meal?.drink_options ?? []).map((item) => item.section).filter(Boolean)
            ),
        ];
    }, [meal?.drink_sections, meal?.drink_options]);

    // 4. Initialize Side and Drink from included defaults
    useEffect(() => {
        if (!meal) return;

        // Set default side
        if (!selectedSide || !userSelectedSideRef.current) {
            setSelectedSide(meal.side || null);
        }

        // Set default drink
        if (!selectedDrink || !userSelectedDrinkRef.current) {
            setSelectedDrink(meal.drink || null);
        }

        // Initialize active drink section to default drink's section (e.g. "Cold Drinks")
        if (!selectedDrinkSection || !userSelectedSectionRef.current) {
            const defaultSection =
                (meal.drink_options ?? []).find((d) => d.id === meal.drink?.id)?.section ||
                meal.drink?.section ||
                (meal.drink_sections && meal.drink_sections[0]) ||
                "";
            setSelectedDrinkSection(defaultSection);
        }
    }, [meal]);

    const burger = meal?.burger;
    const side = meal?.side;
    const drink = meal?.drink;

    const isVegItem = (item) => {
        const ft = String(item?.foodType || item?.food_type || "")
            .toLowerCase()
            .replace("-", "_")
            .replace(" ", "_")
            .trim();
        return ft === "veg";
    };

    // 5. Preserving Backend Dynamic Side Order:
    // Ranked by higher price in each dietary section, with Peri Peri flavor harmony
    const dynamicSideOptions = useMemo(() => {
        return meal?.side_options ?? [];
    }, [meal?.side_options]);

    // Filter drinks for current section
    const visibleDrinks = useMemo(() => {
        const list = meal?.drink_options ?? [];
        if (!selectedDrinkSection) return list;
        return list.filter((item) => item.section === selectedDrinkSection);
    }, [meal?.drink_options, selectedDrinkSection]);

    // Pricing Calculations
    const mealPrice = meal?.meal_price ?? 0;
    const sideExtra = Number(selectedSide?.extra_price) || 0;
    const drinkExtra = Number(selectedDrink?.extra_price) || 0;
    const totalPrice = mealPrice + sideExtra + drinkExtra;

    // Handle Add Meal to Cart
    const handleAddMeal = async () => {
        if (!selectedSide || !selectedDrink) {
            alert("Please select both a side and a drink to complete your meal.");
            return;
        }

        try {
            const response = await fetch("/cart/add-meal", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    meal: {
                        ...meal,
                        side: selectedSide,
                        drink: selectedDrink,
                    },
                    quantity,
                }),
            });

            const data = await response.json();
            if (data.success) {
                syncCart(data);
                notifyCartItemAdded();
                navigate(origin);
            }
        } catch (error) {
            console.error("Failed to add meal to cart:", error);
        }
    };

    // Handle Decline Meal
    const handleDeclineMeal = async () => {
        try {
            await fetch("/meal/decline", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    item_id: burger?.id,
                    product_id: burger?.id,
                }),
            });
        } catch (error) {
            console.warn("Failed to decline meal on backend:", error);
        } finally {
            navigate(origin);
        }
    };

    // Loading State
    if (loading && !meal) {
        return (
            <div className="meal-page">
                <Header title="Meal Builder" />
                <PreviousButton onClick={() => navigate(origin)} />
                <div className="meal-loading-container">
                    <p>Loading your meal options...</p>
                </div>
                <CartContainer />
                <FooterDecoration />
            </div>
        );
    }

    // Error / Empty State
    if (!burger && !loading) {
        return (
            <div className="meal-page">
                <Header title="Meal Builder" />
                <PreviousButton onClick={() => navigate(origin)} />
                <div className="meal-empty-state">
                    <h2 style={{ fontSize: "38px", color: "#4d240d" }}>No Meal Selected</h2>
                    <p style={{ fontSize: "24px", color: "#666" }}>
                        {errorMsg || "Please select a burger from the menu to customize your meal."}
                    </p>
                    <button className="meal-empty-btn" onClick={() => navigate("/")}>
                        Go to Menu
                    </button>
                </div>
                <CartContainer />
                <FooterDecoration />
            </div>
        );
    }

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
                                            src={burger.foodType === "veg" ? vegIcon : nonVegIcon}
                                            alt=""
                                            className="meal-type-icon"
                                        />
                                    )}
                                </h1>
                            </div>

                            <div className="meal-description-area">
                                <p className="meal-short">
                                    {burger.shortDescription || "Customize your meal with your favorite side and drink."}
                                </p>
                            </div>

                            {/* ORIGINAL CLEAN MEAL BADGE */}
                            <div className="meal-badge-area">
                                <div className="meal-badge">
                                    🍔 {mealSize.toUpperCase()} MEAL
                                </div>
                            </div>

                            {/* MEAL SUMMARY */}
                            <div className="meal-summary-area">
                                <h3>Meal Includes</h3>

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
                                    <div>Meal Price</div>
                                    <div>₹{totalPrice}</div>
                                </div>
                            </div>
                        </div>

                        {/* RIGHT PANEL */}
                        <div className="meal-right">
                            <div className="meal-image-wrapper">
                                <img
                                    src={burger.meal_image || burger.image}
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
                            {dynamicSideOptions.map((item) => {
                                const isSelected = selectedSide?.id === item.id;
                                const extraCost = Number(item.extra_price) || 0;

                                return (
                                    <div
                                        key={item.id}
                                        className={`meal-card ${isSelected ? "active" : ""}`}
                                        onClick={() => {
                                            userSelectedSideRef.current = true;
                                            setSelectedSide(item);
                                        }}
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
                                            {extraCost > 0 && (
                                                <span className="upgrade-price">+₹{extraCost}</span>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* ================= DRINKS ================= */}
                        <h2 className="meal-section">
                            2. Choose Your Drink
                        </h2>

                        <div className="drink-filters">
                            {drinkSections.map((section) => (
                                <button
                                    key={section}
                                    className={selectedDrinkSection === section ? "active" : ""}
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
                            {visibleDrinks.map((item) => {
                                const isSelected = selectedDrink?.id === item.id;
                                const extraCost = Number(item.extra_price) || 0;

                                return (
                                    <div
                                        key={item.id}
                                        className={`drink-card ${isSelected ? "active" : ""}`}
                                        onClick={() => {
                                            userSelectedDrinkRef.current = true;
                                            setSelectedDrink(item);
                                        }}
                                    >
                                        <div className="drink-card-image">
                                            <img
                                                src={item.image}
                                                alt={item.name}
                                                className="drink-item-image"
                                            />
                                        </div>

                                        <div className="drink-card-name">
                                            <p>{item.name}</p>
                                        </div>

                                        <div className="drink-card-price">
                                            {extraCost > 0 && (
                                                <span className="upgrade-price">+₹{extraCost}</span>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* QUANTITY SELECTOR */}
                    <div className="meal-quantity-selector">
                        <button
                            className="qty-btn"
                            onClick={() => setQuantity((prev) => (prev > 1 ? prev - 1 : 1))}
                        >
                            −
                        </button>
                        <span className="meal-qty-value">{quantity}</span>
                        <button
                            className="qty-btn"
                            onClick={() => setQuantity((prev) => prev + 1)}
                        >
                            +
                        </button>
                    </div>

                    {/* ADD TO CART BUTTON */}
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
