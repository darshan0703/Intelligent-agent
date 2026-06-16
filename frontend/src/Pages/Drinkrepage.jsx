import "./Drinkrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";
import BackButton from "../components/BackButton";
import { useNavigate } from "react-router-dom";

function Drink() {
  const navigate = useNavigate();

  const freshDrinks = [

    {
      id: 1,
      name: "Cold Coffee",
      description: "Freshly brewed chilled coffee",
      price: 149,
      image: ""
    },

    {
      id: 2,
      name: "Chocolate Shake",
      description: "Rich creamy chocolate shake",
      price: 179,
      image: ""
    }

  ];

  const premiumDrinks = [

    {
      id: 3,
      name: "Mocha Frappe",
      description: "Premium iced mocha delight",
      price: 249,
      image: ""
    },

    {
      id: 4,
      name: "Hazelnut Latte",
      description: "Smooth hazelnut flavor",
      price: 269,
      image: ""
    }

  ];

  const moreDrinks = [

    {
      id: 5,
      name: "Pepsi",
      description: "",
      price: 99,
      image: ""
    },

    {
      id: 6,
      name: "7UP",
      description: "",
      price: 99,
      image: ""
    },

    {
      id: 7,
      name: "Sprite",
      description: "",
      price: 99,
      image: ""
    },

    {
      id: 8,
      name: "Orange Juice",
      description: "",
      price: 129,
      image: ""
    }

  ];

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
      {/* FRESH DRINKS */}
      <ProductCard
        product={freshDrinks[0]}
        variant="large"
        className="card-1"
      />

      <ProductCard
        product={freshDrinks[1]}
        variant="large"
        className="card-2"
      />

      {/* PREMIUM */}
      <ProductCard
        product={premiumDrinks[0]}
        variant="large"
        className="card-3"
      />

      <ProductCard
        product={premiumDrinks[1]}
        variant="large"
        className="card-4"
      />

      {/* MORE OPTIONS */}
      <ProductCard
        product={moreDrinks[0]}
        variant="small"
        className="card-5"
      />

      <ProductCard
        product={moreDrinks[1]}
        variant="small"
        className="card-6"
      />

      <ProductCard
        product={moreDrinks[2]}
        variant="small"
        className="card-7"
      />

      <ProductCard
        product={moreDrinks[3]}
        variant="small"
        className="card-8"
      />

      {/* TITLES */}

      <p className="fresh-text">
        Freshly Made Drinks
      </p>

      <p className="fresh-text2">
       Popular & perfect right now
      </p>

      <div className="thin-line-2"></div>

      <p className="premium-text">
        Premium Beverages
      </p>

      <p className="premium-text2">
        Indulge in our most loved shakes & drinks
      </p>

      <div className="thin-line-3"></div>

      <p className="more-text">
    More Drink Options
  </p>
        
<div className="more-header">

        <button
          className="view-all-btn"
          onClick={() => navigate("/drinkmenu")}
        >
          View All →
        </button>

</div>

        <CartContainer
  itemCount={0}
  total={538}
/>

    </div>
  );
}

export default Drink;