import "./Mealpage.css";
import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";
import { syncScreen } from "../services/screenService";
import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";
import FooterDecoration from "../components/FooterDecoration";

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function MealPage() {
    const { state } = useLocation();
    const navigate = useNavigate();
    const origin = state?.origin || "/";
    const meal = state?.meal;

    const { foodPreference } = useKiosk();

    const burger = meal?.burger;
    const side = meal?.side;
    const drink = meal?.drink;

    const mealSize = meal?.size || "Medium";
    const { syncCart } = useCart();
    const [quantity, setQuantity] = useState(1);

    const isVegIntent = foodPreference === "veg" || burger?.foodType === "veg";

    const filteredSideOptions = (meal?.side_options ?? []).filter((item) => {
        if (isVegIntent) {
            const ft = (item.foodType || item.type || item.food_type || "").toLowerCase();
            return ft === "veg" || (!ft.includes("non") && !/chicken|wings|nugget|bone/i.test(item.name || ""));
        }
        if (foodPreference === "non veg" || foodPreference === "non_veg") {
            const ft = (item.foodType || item.type || item.food_type || "").toLowerCase();
            return ft.includes("non") || /chicken|wings|nugget|bone/i.test(item.name || "");
        }
        return true;
    });

    const [selectedSide, setSelectedSide] = useState(() => {
        if (isVegIntent && side) {
            const ft = (side.foodType || side.type || side.food_type || "").toLowerCase();
            const isNonVeg = ft.includes("non") || /chicken|wings|nugget|bone/i.test(side.name || "");
            if (isNonVeg && filteredSideOptions.length > 0) {
                return filteredSideOptions[0];
            }
        }
        return side;
    });

    useEffect(() => {
        syncScreen("meal_builder");
    }, []);

    useEffect(() => {
        if (isVegIntent && selectedSide) {
            const ft = (selectedSide.foodType || selectedSide.type || selectedSide.food_type || "").toLowerCase();
            const isNonVeg = ft.includes("non") || /chicken|wings|nugget|bone/i.test(selectedSide.name || "");
            if (isNonVeg && filteredSideOptions.length > 0) {
                setSelectedSide(filteredSideOptions[0]);
            }
        }
    }, [foodPreference, isVegIntent, filteredSideOptions, selectedSide]);

    const drinkSections = [
        ...new Set(
            (meal?.drink_options ?? []).map(
                item => item.section
            )
        )
    ];

    const [selectedDrinkSection, setSelectedDrinkSection] =
        useState(drinkSections[0] || "");

    const [selectedDrink, setSelectedDrink] =
        useState(drink);

    const visibleDrinks =
        (meal?.drink_options ?? []).filter(
            item =>
                item.section ===
                selectedDrinkSection
        );

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

    const handleAddMeal = async () => {
        try {
            const response = await fetch(
                `${API_BASE_URL}/cart/add-meal`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        meal: {
                            ...meal,
                            side: selectedSide,
                            drink: selectedDrink
                        },
                        quantity
                    })
                }
            );

            const data = await response.json();
            if (data.success) {
                syncCart(data);
                navigate(origin);
            }
        } catch (error) {
            console.error("Add meal error:", error);
        }
    };

    const handleDeclineMeal = async () => {
        try {
            const response = await fetch(
                `${API_BASE_URL}/meal/decline`,
                {
                    method: "POST",
                }
            );
            const data = await response.json();
            console.log("MEAL DECLINED:", data);
        } catch (error) {
            console.error("Failed to decline meal:", error);
        } finally {
            navigate(origin);
        }
    };
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

                                    {(() => {

                                        const words = burger.name.split(" ");

                                        const midpoint = Math.ceil(
                                            words.length / 2
                                        );

                                        return (
                                            <>

                                                {words
                                                    .slice(0, midpoint)
                                                    .join(" ")}

                                                <br />

                                                {words
                                                    .slice(midpoint)
                                                    .join(" ")}

                                            </>
                                        );

                                    })()}

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

                                    {burger.shortDescription || burger.short_description || burger.description || "Flame-grilled meal paired with your choice of sides and drink."}

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

                                        🍟 {selectedSide?.name}

                                    </div>

                                    <div className="meal-item-right">

                                        {sideExtra > 0
                                            ? `+₹${sideExtra}`
                                            : "₹0"}

                                    </div>

                                </div>

                                <div className="meal-include-item">

                                    <div className="meal-item-left">

                                        🥤 {selectedDrink?.name}

                                    </div>

                                    <div className="meal-item-right">

                                        {drinkExtra > 0
                                            ? `+₹${drinkExtra}`
                                            : "₹0"}

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

                            {(filteredSideOptions.length > 0 ? filteredSideOptions : meal?.side_options ?? []).map((item) => (

                                <div

                                    key={item.id}

                                    className={`meal-card ${selectedSide?.id === item.id
                                            ? "active"
                                            : ""
                                        }`}

                                    onClick={() =>
                                        setSelectedSide(item)
                                    }

                                >

                                    <div className="meal-card-image">

                                        <img
                                            src={item.image}
                                            alt={item.name}
                                            className="meal-item-image"
                                        />

                                    </div>

                                    <div className="meal-card-name">

                                        <p>

                                            {item.name}

                                        </p>

                                    </div>

                                    <div className="meal-card-price">

                                        {item.extra_price > 0 ? (

                                            <span className="upgrade-price">

                                                +₹{item.extra_price}

                                            </span>

                                        ) : (

                                            <span className="upgrade-price" style={{ color: "#2e7d32" }}>

                                                Included

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

                                    onClick={() =>
                                        setSelectedDrinkSection(section)
                                    }

                                >

                                    {section}

                                </button>

                            ))}

                        </div>

                        <div className="drink-grid">

                            {visibleDrinks.map((item) => (

                                <div

                                    key={item.id}

                                    className={`drink-card ${selectedDrink?.id === item.id
                                            ? "active"
                                            : ""
                                        }`}

                                    onClick={() =>
                                        setSelectedDrink(item)
                                    }

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

                                        {item.extra_price > 0 ? (

                                            <span className="upgrade-price">

                                                +₹{item.extra_price}

                                            </span>

                                        ) : (

                                            <span className="upgrade-price" style={{ color: "#2e7d32" }}>

                                                Included

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
                    >
                        {`Add Meal To Cart • ₹${totalPrice * quantity}`}
                    </button>

                </>

            )}

            {!burger && (
              <div style={{ textAlign: "center", marginTop: "140px", color: "#666", padding: "20px" }}>
                <h2 style={{ fontSize: "28px", color: "#d62300" }}>No Meal Selected</h2>
                <p style={{ marginTop: "12px", fontSize: "18px" }}>Please select a burger from the menu to build your custom meal.</p>
                <button
                  className="meal-add-cart-btn"
                  style={{ marginTop: "24px", maxWidth: "260px", margin: "24px auto" }}
                  onClick={() => navigate("/burgermenu")}
                >
                  Browse Burgers →
                </button>
              </div>
            )}

            <CartContainer />

            <FooterDecoration />

        </div>

    );

}

export default MealPage;