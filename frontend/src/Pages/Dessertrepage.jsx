import "./Dessertrepage.css";

import Header from "../components/Header";
import ProductCard from "../components/ProductCard";
import CartContainer from "../components/CartContainer";


import fire from "../assets/images/fire.png";
import crown from "../assets/images/crown.png";
import BackButton from "../components/BackButton";
import { useNavigate } from "react-router-dom";

function Dessert() {

  const navigate = useNavigate();

  const freshDesserts = [

    {
      id: 1,
      name: "Chocolate Lava Cake",
      description: "Warm gooey chocolate delight",
      price: 149,
      image: ""
    },

    {
      id: 2,
      name: "Brownie Sundae",
      description: "Rich brownie with ice cream",
      price: 179,
      image: ""
    }

  ];

  const premiumDesserts = [

    {
      id: 3,
      name: "Belgian Chocolate Shake",
      description: "Premium thick chocolate shake",
      price: 249,
      image: ""
    },

    {
      id: 4,
      name: "Lotus Biscoff Sundae",
      description: "Creamy biscoff indulgence",
      price: 269,
      image: ""
    }

  ];

  const moreDesserts = [

    {
      id: 5,
      name: "Vanilla Cone",
      description: "",
      price: 59,
      image: ""
    },

    {
      id: 6,
      name: "Chocolate Cone",
      description: "",
      price: 69,
      image: ""
    },

    {
      id: 7,
      name: "Soft Serve",
      description: "",
      price: 79,
      image: ""
    },

    {
      id: 8,
      name: "Mini Brownie",
      description: "",
      price: 99,
      image: ""
    }

  ];

  return (

    <div className="dessert-page">

    
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
      <Header title="Choose Your Dessert" />
      <BackButton />
      {/* FRESH PICKS */}
      <ProductCard
        product={freshDesserts[0]}
        variant="large"
        className="card-1"
      />

      <ProductCard
        product={freshDesserts[1]}
        variant="large"
        className="card-2"
      />

      {/* PREMIUM */}
      <ProductCard
        product={premiumDesserts[0]}
        variant="large"
        className="card-3"
      />

      <ProductCard
        product={premiumDesserts[1]}
        variant="large"
        className="card-4"
      />

      {/* MORE OPTIONS */}
      <ProductCard
        product={moreDesserts[0]}
        variant="small"
        className="card-5"
      />

      <ProductCard
        product={moreDesserts[1]}
        variant="small"
        className="card-6"
      />

      <ProductCard
        product={moreDesserts[2]}
        variant="small"
        className="card-7"
      />

      <ProductCard
        product={moreDesserts[3]}
        variant="small"
        className="card-8"
      />

      {/* TITLES */}

      <p className="fresh-text">
        Sweet Picks For You
      </p>

      <p className="fresh-text2">
        Popular & perfect for you     
      </p>

      <div className="thin-line-2"></div>

      <p className="premium-text">
        Premium Desserts
      </p>

      <p className="premium-text2">
        Rich,indulgent & made to delight
      </p>

      <div className="thin-line-3"></div>

      <p className="more-text">
        More Dessert Options
      </p>

        
 <div className="more-header">



  <button className="view-all-btn"
  onClick={() => navigate("/dessertmenu")}
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

export default Dessert;