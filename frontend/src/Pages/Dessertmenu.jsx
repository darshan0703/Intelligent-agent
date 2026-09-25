import "./menu.css";

import Header from "../components/Header";
import BackButton from "../components/BackButton";
import Menusidebar from "../components/Menusidebar";
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

function Dessertmenu() {

  const [dessertSections, setDessertSections] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/menu/desserts`)
      .then((res) => res.json())
      .then(setDessertSections);
  }, []);

  const menuContentRef = useRef(null);

  const sectionRefs = useRef({});

  const [activeCategory, setActiveCategory] =
    useState("");

  const [quickFilter, setQuickFilter] =
    useState("all");

  const filterProducts = (products) => {
    if (!products || !Array.isArray(products)) {
      return [];
    }

    let list = products;
    if (quickFilter === "bestseller") {
      list = list.filter(
        p => (p.badge && p.badge.toLowerCase().includes("bestseller")) || /sundae|lava|mousse|pie|shake/i.test(p.name)
      );
    } else if (quickFilter === "value") {
      list = list.filter(
        p => Number(p.price) <= 99 || (p.badge && p.badge.toLowerCase().includes("value"))
      );
    } else if (quickFilter === "veg") {
      list = list.filter(
        p => p.type !== "non veg" && p.foodType !== "non veg"
      );
    }

    return list;
  };

  const safeSections = Array.isArray(dessertSections) ? dessertSections : [];
  const visibleSections = safeSections
    .map(section => ({
      ...section,
      products: filterProducts(section.products)
    }))
    .filter(section => section.products.length > 0);

  const categories = visibleSections.map(
    section => section.title
  );

  useEffect(() => {
    if (
      visibleSections.length > 0 &&
      !visibleSections.some(
        section => section.title === activeCategory
      )
    ) {
      setActiveCategory(visibleSections[0].title);
    }
  }, [visibleSections]);

  const scrollToCategory = (categoryTitle) => {

    setActiveCategory(categoryTitle);

    const section =
      visibleSections.find(
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

  }, [visibleSections]);

  return (

    <div className="menu-page">

      <Header
        title="Choose Your Dessert"
      />

      <BackButton />

      <Menusidebar
        categories={categories}
        activeCategory={
          activeCategory
        }
        onCategoryClick={
          scrollToCategory
        }
      />

      <div
        className="menu-content"
        ref={menuContentRef}
      >

        <SpotlightShelf
          category="dessert"
          activeQuickFilter={quickFilter}
          onQuickFilterSelect={(f) => setQuickFilter(prev => prev === f ? "all" : f)}
        />

        {visibleSections.map(
          section => (

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
                products={
                  section.products
                }
              />

            </div>

          )
        )}

      </div>

      <CartContainer />

    </div>

  );

}

export default Dessertmenu;
