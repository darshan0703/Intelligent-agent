import "./Sidesrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";

import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";
import BackButton from "../components/BackButton";
import { useNavigate } from "react-router-dom";


function Sides() {
    const navigate = useNavigate();


  const hotSides = [

    {
      id: 1,
      name: "Peri Peri Fries",
      description: "Crispy fries with peri peri seasoning",
      price: 129,
      image: ""
    },

    {
      id: 2,
      name: "Cheesy Loaded Fries",
      description: "Loaded with creamy cheese",
      price: 169,
      image: ""
    }

  ];

  const premiumSides = [

    {
      id: 3,
      name: "Chicken Nuggets",
      description: "Premium crispy nuggets",
      price: 249,
      image: ""
    },

    {
      id: 4,
      name: "Chicken Wings",
      description: "Juicy spicy wings",
      price: 299,
      image: ""
    }

  ];

  const moreSides = [

    {
      id: 5,
      name: "Hash Browns",
      description: "",
      price: 89,
      image: ""
    },

    {
      id: 6,
      name: "Onion Rings",
      description: "",
      price: 109,
      image: ""
    },

    {
      id: 7,
      name: "Veg Nuggets",
      description: "",
      price: 119,
      image: ""
    },

    {
      id: 8,
      name: "Cheese Dip",
      description: "",
      price: 49,
      image: ""
    }

  ];

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
      <Header title="Choose Your Sides" />
      <BackButton />

      {/* HOT PICKS */}
      <ProductCard
        product={hotSides[0]}
        variant="large"
        className="card-1"
      />

      <ProductCard
        product={hotSides[1]}
        variant="large"
        className="card-2"
      />

      {/* PREMIUM */}
      <ProductCard
        product={premiumSides[0]}
        variant="large"
        className="card-3"
      />

      <ProductCard
        product={premiumSides[1]}
        variant="large"
        className="card-4"
      />

      {/* MORE OPTIONS */}
      <ProductCard
        product={moreSides[0]}
        variant="small"
        className="card-5"
      />

      <ProductCard
        product={moreSides[1]}
        variant="small"
        className="card-6"
      />

      <ProductCard
        product={moreSides[2]}
        variant="small"
        className="card-7"
      />

      <ProductCard
        product={moreSides[3]}
        variant="small"
        className="card-8"
      />

      {/* TITLES */}

      <p className="fresh-text">
        Hot & Crispy Picks
      </p>

      <p className="fresh-text2">
        Freshly prepared favorites
      </p>

      <div className="thin-line-2"></div>

      <p className="premium-text">
        Premium Sides
      </p>

      <p className="premium-text2">
        Perfect add-ons for every meal
      </p>

      <div className="thin-line-3"></div>

<p className="more-text">
    More Sides Options
  </p>
        
<div className="more-header">

  <p className="more-text">
    More Side Options
  </p>

  <button className="view-all-btn"
  onClick={() => navigate("/sidesmenu")}>
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

export default Sides;
