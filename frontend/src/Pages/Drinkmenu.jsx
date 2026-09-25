import "./menu.css";

import Header from "../components/Header";
import BackButton from "../components/BackButton";
import Menusidebar from "../components/Menusidebar";
import Menufilters from "../components/Menufilters";
import CartContainer from "../components/CartContainer";
import MenuSection from "../components/MenuSection";
import SpotlightShelf from "../components/SpotlightShelf";

import {
  useRef,
  useState,
  useEffect
} from "react";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function Drinkmenu() {

  const [drinkSections, setDrinkSections] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/menu/drinks`)
        .then((res) => res.json())
        .then(setDrinkSections);
  }, []);

  const menuContentRef = useRef(null);

  const sectionRefs = useRef({});

  const [activeCategory, setActiveCategory] =
    useState("");

  const [activeFilter, setActiveFilter] =
    useState("both");

  const [quickFilter, setQuickFilter] =
    useState("all");

  const filterProducts = (products) => {
    if (!products || !Array.isArray(products)) {
      return [];
    }

    let list = products;
    if (activeFilter !== "both") {
      list = list.filter(
        product => product.type === activeFilter || product.serving_type === activeFilter || product.servingType === activeFilter
      );
    }

    if (quickFilter === "bestseller") {
      list = list.filter(
        p => (p.badge && p.badge.toLowerCase().includes("bestseller")) || /coffee|coke|shake|frost/i.test(p.name)
      );
    } else if (quickFilter === "value") {
      list = list.filter(
        p => Number(p.price) <= 99 || (p.badge && p.badge.toLowerCase().includes("value"))
      );
    } else if (quickFilter === "spicy") {
      const spicyList = list.filter(p => /ginger|masala|lemon/i.test(p.name));
      if (spicyList.length > 0) list = spicyList;
    } else if (quickFilter === "veg") {
      list = list.filter(
        p => p.type !== "non veg" && p.foodType !== "non veg"
      );
    }

    return list;
  };

  const safeSections = Array.isArray(drinkSections) ? drinkSections : [];
  const visibleSections = safeSections
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
          sectionRefs.current[
            section.id
          ];

        if (
          element &&
          scrollPosition >=
            element.offsetTop
        ) {

          currentCategory =
            section.title;

        }

      });

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

  }, [activeFilter,drinkSections]);

  return (

    <div className="menu-page">

      <Header title="Choose Your Drink" />

      <BackButton />

      <Menusidebar
        categories={categories}
        activeCategory={activeCategory}
        onCategoryClick={scrollToCategory}
      />

      <Menufilters
        filters={[
          "both",
          "cold",
          "hot"
        ]}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
      />

      <div
        className="menu-content"
        ref={menuContentRef}
      >

        <SpotlightShelf
          category="drink"
          activeQuickFilter={quickFilter}
          onQuickFilterSelect={(f) => setQuickFilter(prev => prev === f ? "all" : f)}
        />

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

    </div>

  );

}

export default Drinkmenu;
