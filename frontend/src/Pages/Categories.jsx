import "./Categories.css";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import Header from "../components/Header";


import cb from "../assets/images/container burger.png";
import cd from "../assets/images/container drinks.png";
import cr from "../assets/images/container recommend.png";
import cf from "../assets/images/container fresh.png";
import co from "../assets/images/container offers.png";
import cl from "../assets/images/container light.png";
import CartContainer from "../components/CartContainer";

function Categories() {

  const navigate = useNavigate();

  const phrases = [
    '"What\'s special today?"',
    '"Add Peri Peri Fries"',
    '"Can I have a Cold Coffee?"'
  ];

  const [currentPhrase, setCurrentPhrase] = useState(0);

  useEffect(() => {

    const interval = setInterval(() => {

      setCurrentPhrase((prev) =>
        (prev + 1) % phrases.length
      );

    }, 2000);

    return () => clearInterval(interval);

  }, []);

  return (

    <div className="app-wrapper">

      <div className="header-glow"></div>

      <div className="categories-page">


        {/* HEADER */}
        <Header title="Welcome to Burger KING!" />

        {/* CONTAINERS */}
        <img
          src={cb}
          alt="container burger"
          className="cb-image"
          onClick={() => navigate("/burgers")}
        />

        <img
          src={cd}
          alt="container drinks"
          className="cd-image"
          onClick={() => navigate("/drinks")}
        />

        <img
          src={cr}
          alt="container recommend"
          className="cr-image"
        />

        <img
          src={cf}
          alt="container fresh"
          className="cf-image"
        />

        <img
          src={co}
          alt="container offers"
          className="co-image"
        />

        <img
          src={cl}
          alt="container light"
          className="cl-image"
        />

        {/* SECOND LINE */}
        <div className="thin-line-two"></div>

        {/* TRY PHRASES */}
        <p className="try-text">
          Try these phrases :
        </p>

        <p className="rotating-phrase">
          {phrases[currentPhrase]}
        </p>
      


<CartContainer
  itemCount={0}
  total={538}
/>

      </div>

    </div>
  );
}

export default Categories;