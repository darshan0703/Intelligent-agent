import "./Burgerrepage.css";

import { useNavigate } from "react-router-dom";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";
import CartContainer from "../components/CartContainer";
import BackButton from "../components/BackButton";

function Burger() {

  const navigate = useNavigate();

  const expiryRecommendations = [

    {
      id: 1,
      name: "Chicken Whopper",
      description: "Flame grilled chicken burger",
      price: 189,
      image: ""
    },

    {
      id: 2,
      name: "Veg Whopper",
      description: "Fresh veg patty",
      price: 149,
      image: ""
    }

  ];

  const premiumRecommendations = [

    {
      id: 3,
      name: "Korean BBQ Whopper",
      description: "Premium Korean sauce burger",
      price: 349,
      image: ""
    },

    {
      id: 4,
      name: "Double Patty Supreme",
      description: "Loaded premium burger",
      price: 399,
      image: ""
    }

  ];

  const upsellRecommendations = [

    {
      id: 5,
      name: "Crispy Chicken Burger",
      description: "Crunchy chicken burger",
      price: 199,
      image: ""
    },

    {
      id: 6,
      name: "Cheese Burst Burger",
      description: "Extra cheese loaded",
      price: 229,
      image: ""
    },

    {
      id: 7,
      name: "Spicy Paneer Burger",
      description: "Hot spicy paneer delight",
      price: 179,
      image: ""
    },

    {
      id: 8,
      name: "Classic Veg Burger",
      description: "Classic BK style",
      price: 129,
      image: ""
    }

  ];

  return (

    <div className="burger-page">

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
      <Header title="Choose Your Burger" />

      <BackButton />

      {/* RECOMMENDATIONS */}

      <ProductCard
        product={expiryRecommendations[0]}
        variant="large"
        className="card-1"
      />

      <ProductCard
        product={expiryRecommendations[1]}
        variant="large"
        className="card-2"
      />

      {/* PREMIUM */}

      <ProductCard
        product={premiumRecommendations[0]}
        variant="large"
        className="card-3"
      />

      <ProductCard
        product={premiumRecommendations[1]}
        variant="large"
        className="card-4"
      />

      {/* MORE OPTIONS */}

      <ProductCard
        product={upsellRecommendations[0]}
        variant="small"
        className="card-5"
      />

      <ProductCard
        product={upsellRecommendations[1]}
        variant="small"
        className="card-6"
      />

      <ProductCard
        product={upsellRecommendations[2]}
        variant="small"
        className="card-7"
      />

      <ProductCard
        product={upsellRecommendations[3]}
        variant="small"
        className="card-8"
      />

      {/* SECTION TITLES */}

      <p className="Recommendation-text">
        Fresh Picks For You
      </p>

      <p className="Recommendation-text2">
        Recommended based on availability
      </p>

      <div className="thin-line-2"></div>

      <p className="Premium-text">
        Premium Collection
      </p>

      <p className="Premium-text2">
        Handpicked just for you
      </p>

      <div className="thin-line-3"></div>

      {/* MORE OPTIONS HEADER */}

      <div className="more-header">

        <p className="more-text">
          More Burger Options
        </p>

        <button
          className="view-all-btn"
          onClick={() => navigate("/burgermenu")}
        >
          View All →
        </button>

      </div>

      {/* CART */}

      <CartContainer
        itemCount={0}
        total={538}
      />

    </div>

  );
}

export default Burger;