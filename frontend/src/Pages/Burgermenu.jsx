
import "./menu.css";

import Header from "../components/Header";
import BackButton from "../components/BackButton";
import Menusidebar from "../components/Menusidebar";
import Menufilters from "../components/Menufilters";
import CartContainer from "../components/CartContainer";
import MenuSection from "../components/MenuSection";
import FooterDecoration from "../components/FooterDecoration";

import {
  useRef,
  useState,
  useEffect
} from "react";
import { useLocation } from "react-router-dom";
import { useKiosk } from "../context/KioskContext";
import { syncScreen } from "../services/screenService";

function Burgermenu() {
  const location = useLocation();
  const { foodPreference, setFoodPreference } = useKiosk();

  const [burgerSections, setBurgerSections] = useState([]);
  const [activeFilter, setActiveFilter] = useState(
    location.state?.activeFilter || foodPreference || "both"
  );

  useEffect(() => {
    if (location.state?.activeFilter) {
      setActiveFilter(location.state.activeFilter);
    } else if (foodPreference) {
      setActiveFilter(foodPreference);
    }
  }, [location.state?.activeFilter, foodPreference]);

  useEffect(() => {
    const prefParam = activeFilter !== "both" ? `?preference=${activeFilter}` : "";
    fetch(`/menu/burgers${prefParam}`)
      .then((res) => res.json())
      .then(setBurgerSections)
      .catch((err) => console.warn("Failed to fetch burgers:", err));
  }, [activeFilter]);

  useEffect(() => {
    syncScreen("burger_menu");
  }, []);

  const menuContentRef = useRef(null);
  const sectionRefs = useRef({});

  const [activeCategory, setActiveCategory] = useState("");

  const handleFilterChange = (filter) => {
    setActiveFilter(filter);
    if (setFoodPreference) {
      setFoodPreference(filter);
    }
  };

  const filterProducts = (products) => {
    if (activeFilter === "both") {
      return products;
    }
    return products.filter(
      (product) => (product.type || product.foodType || "").toLowerCase() === activeFilter.toLowerCase()
    );
  };

  const visibleSections = burgerSections
    .map(section => ({
      ...section,
      products: filterProducts(
        section.products
      )
    }))
    .filter(
      section =>
        section.products.length > 0
    );

  const categories = visibleSections.map(
    section => section.title
  );

  useEffect(() => {

    if (
      visibleSections.length > 0 &&
      !visibleSections.some(
        section =>
          section.title === activeCategory
      )
    ) {

      setActiveCategory(
        visibleSections[0].title
      );

    }

  }, [activeFilter, visibleSections]);

  const scrollToCategory = (categoryTitle) => {

    setActiveCategory(categoryTitle);

    const section = visibleSections.find(
      section =>
        section.title === categoryTitle
    );

    if (!section) return;

    sectionRefs.current[
      section.id
    ]?.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });

  };

  useEffect(() => {

    const menu = menuContentRef.current;

    if (!menu) return;

    const handleScroll = () => {

      const scrollPosition =
        menu.scrollTop +
        menu.clientHeight / 4;

      let currentCategory =
        visibleSections[0]?.title;

      visibleSections.forEach(section => {

        const element =
          sectionRefs.current[section.id];

        if (
          element &&
          scrollPosition >= element.offsetTop
        ) {

          currentCategory =
            section.title;

        }

      });

      // Fix for last category

      const isNearBottom =
        menu.scrollTop +
          menu.clientHeight >=
        menu.scrollHeight - 50;

      if (isNearBottom) {

        currentCategory =
          visibleSections[
            visibleSections.length - 1
          ]?.title;

      }

      setActiveCategory(prev =>
        prev !== currentCategory
          ? currentCategory
          : prev
      );

    };

    handleScroll();

    menu.addEventListener(
      "scroll",
      handleScroll
    );

    return () => {

      menu.removeEventListener(
        "scroll",
        handleScroll
      );

    };

  }, [activeFilter, visibleSections]);

  return (

    <div className="menu-page">

      <Header title="Choose Your Burger" />

      <BackButton />

      <Menusidebar
        categories={categories}
        activeCategory={activeCategory}
        onCategoryClick={scrollToCategory}
      />

      <Menufilters
        filters={[
          "both",
          "veg",
          "non veg"
        ]}
        activeFilter={activeFilter}
        onFilterChange={handleFilterChange}
      />

      <div
        className="menu-content"
        ref={menuContentRef}
      >

        {visibleSections.map(section => (

          <div
            key={section.id}
            ref={(el) => {
              sectionRefs.current[
                section.id
              ] = el;
            }}
          >

            <MenuSection
              title={section.title}
              products={section.products}
            />

          </div>

        ))}

      </div>

      <CartContainer />

      <FooterDecoration />

    </div>

  );

}

export default Burgermenu;
