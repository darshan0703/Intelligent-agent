import "./MealPage.css";
import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import Header from "../components/Header";
import PreviousButton from "../components/PreviousButton";
import CartContainer from "../components/CartContainer";

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

  const mealSize = meal?.size || "Medium";
  const { syncCart } = useCart();
  const [quantity, setQuantity] = useState(1);

    const [selectedSide, setSelectedSide] = useState(side);

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

        console.log("Burger:", burger);
const handleAddMeal = async () => {

    try {

        const response = await fetch(
            "http://localhost:8000/cart/add-meal",
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
            navigate(origin);
        }

    } catch (error) {

        console.error(error);

    }

};
    return (

        <div className="meal-page">

            <Header title="Meal Builder" />

            <PreviousButton />

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

    {meal.side_options?.map((item) => (

        <div

            key={item.id}

            className={`meal-card ${
                selectedSide?.id === item.id
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

    {visibleDrinks.map((item) => (

        <div

            key={item.id}

            className={`drink-card ${
                selectedDrink?.id === item.id
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

</div>

);

}

export default MealPage;