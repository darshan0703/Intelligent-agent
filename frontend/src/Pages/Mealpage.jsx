import "./Mealpage.css";
import React, { useState, useMemo, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";
import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";
import FooterDecoration from "../components/FooterDecoration";

import vegIcon from "../assets/images/veg.png";
import nonVegIcon from "../assets/images/nonveg.png";

function MealPage() {
    const { state } = useLocation();
    const navigate = useNavigate();
    const origin = state?.origin || "/";
    const meal = state?.meal;

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
        const ft = String(item?.foodType || item?.food_type || "").toLowerCase().trim();
        const name = String(item?.name || "").toLowerCase();
        if (ft.includes("non") || ["chicken", "wings", "nugget", "boneless", "mutton", "fish"].some((k) => name.includes(k))) {
            return false;
        }
        return true;
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

    const sortedSideOptions = useMemo(() => {
        const options = meal?.side_options ?? [];
        return [...options].sort((a, b) => {
            const aInCart = isItemInCart(a) ? 1 : 0;
            const bInCart = isItemInCart(b) ? 1 : 0;
            if (aInCart !== bInCart) return aInCart - bInCart; // cart exclusion at last

            const aIsVeg = isVegItem(a);
            const bIsVeg = isVegItem(b);

            if (effectivePref === "veg") {
                const aPri = aIsVeg ? 0 : 1;
                const bPri = bIsVeg ? 0 : 1;
                if (aPri !== bPri) return aPri - bPri; // Veg first, non-veg after
            } else if (effectivePref === "non_veg") {
                const aPri = aIsVeg ? 1 : 0;
                const bPri = bIsVeg ? 1 : 0;
                if (aPri !== bPri) return aPri - bPri; // Non-veg first, veg after
            }

            // Default first
            const aDef = a.id === side?.id ? 0 : 1;
            const bDef = b.id === side?.id ? 0 : 1;
            if (aDef !== bDef) return aDef - bDef;

            return (Number(a.extra_price) || 0) - (Number(b.extra_price) || 0);
        });
    }, [meal?.side_options, effectivePref, cart, side]);

    useEffect(() => {
        if (!selectedSide && sortedSideOptions.length > 0) {
            setSelectedSide(sortedSideOptions[0]);
        } else if (selectedSide && isItemInCart(selectedSide)) {
            const firstUncarted = sortedSideOptions.find((s) => !isItemInCart(s));
            if (firstUncarted) setSelectedSide(firstUncarted);
        } else if (effectivePref === "veg" && selectedSide && !isVegItem(selectedSide)) {
            const firstVeg = sortedSideOptions.find((s) => isVegItem(s) && !isItemInCart(s));
            if (firstVeg) setSelectedSide(firstVeg);
        }
    }, [sortedSideOptions, effectivePref, cart]);

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

    const sortedVisibleDrinks = useMemo(() => {
        return [...visibleDrinks].sort((a, b) => {
            const aInCart = isItemInCart(a) ? 1 : 0;
            const bInCart = isItemInCart(b) ? 1 : 0;
            if (aInCart !== bInCart) return aInCart - bInCart; // cart exclusion at last

            const aDef = a.id === drink?.id ? 0 : 1;
            const bDef = b.id === drink?.id ? 0 : 1;
            if (aDef !== bDef) return aDef - bDef;

            return (Number(a.extra_price) || 0) - (Number(b.extra_price) || 0);
        });
    }, [visibleDrinks, cart, drink]);

    useEffect(() => {
        if (!selectedDrink && sortedVisibleDrinks.length > 0) {
            setSelectedDrink(sortedVisibleDrinks[0]);
        } else if (selectedDrink && isItemInCart(selectedDrink)) {
            const firstUncarted = sortedVisibleDrinks.find((d) => !isItemInCart(d));
            if (firstUncarted) setSelectedDrink(firstUncarted);
        }
    }, [sortedVisibleDrinks, cart]);

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

        try {

            const response = await fetch(
                "/cart/add-meal",
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

            console.log("ADD MEAL:", data);

            if (data.success) {
                syncCart(data);
                notifyCartItemAdded();
                navigate(origin);
            }

        } catch (error) {

            console.error(error);

        }

    };
    const handleDeclineMeal = async () => {
        try {
            const response = await fetch(
                "/meal/decline",
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

                            {sortedSideOptions.map((item) => (

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

                                    onClick={() =>
                                        setSelectedDrinkSection(section)
                                    }

                                >

                                    {section}

                                </button>

                            ))}

                        </div>

                        <div className="drink-grid">

                            {sortedVisibleDrinks.map((item) => (

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
                    >
                        {`Add Meal To Cart • ₹${totalPrice * quantity}`}
                    </button>

                </>

            )}

            <CartContainer />

            <FooterDecoration />

        </div>

    );

}

export default MealPage;