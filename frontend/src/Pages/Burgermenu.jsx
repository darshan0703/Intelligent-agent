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
import { useLocation } from "react-router-dom";
import { useKiosk } from "../context/KioskContext";
import { syncScreen } from "../services/screenService";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function Burgermenu() {
  const location = useLocation();
  const { foodPreference, setFoodPreference } = useKiosk();

  const [activeFilter, setActiveFilter] = useState(() => {
    if (location.state?.activeFilter) return location.state.activeFilter;
    if (foodPreference && foodPreference !== "both") return foodPreference;
    return "both";
  });

  const [burgerSections, setBurgerSections] = useState([]);

  useEffect(() => {
    const isFiltered = activeFilter && activeFilter !== "both";
    const queryParam = isFiltered ? `?preference=${encodeURIComponent(activeFilter)}` : "";
    fetch(`${API_BASE_URL}/menu/burgers${queryParam}`)
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) setBurgerSections(data);
        })
        .catch(err => console.warn("Failed to fetch burgers:", err));
  }, [activeFilter]);

  useEffect(() => {
    syncScreen("burger_menu");
  }, []);

  const menuContentRef = useRef(null);
  const sectionRefs = useRef({});

  const [activeCategory, setActiveCategory] = useState("");

  useEffect(() => {
    if (foodPreference) {
      setActiveFilter(foodPreference);
    }
  }, [foodPreference]);

  const handleFilterChange = (f) => {
    setActiveFilter(f);
    if (setFoodPreference) setFoodPreference(f);
  };

  const [quickFilter, setQuickFilter] = useState("all");

  const filterProducts = (products) => {
    if (!products || !Array.isArray(products)) {
      return [];
    }

    let list = products;
    if (activeFilter !== "both") {
      list = list.filter(
        product => product.type === activeFilter || product.foodType === activeFilter || product.food_type === activeFilter
      );
    }

    if (quickFilter === "bestseller") {
      list = list.filter(
        p => (p.badge && p.badge.toLowerCase().includes("bestseller")) || /whopper|royale/i.test(p.name)
      );
    } else if (quickFilter === "value") {
      list = list.filter(
        p => Number(p.price) <= 99 || (p.badge && p.badge.toLowerCase().includes("value"))
      );
    } else if (quickFilter === "spicy") {
      list = list.filter(
        p => (p.badge && /spicy|heat/i.test(p.badge)) || /spicy|peri|fiery/i.test(p.name)
      );
    } else if (quickFilter === "veg") {
      list = list.filter(
        p => p.type === "veg" || p.foodType === "veg" || p.food_type === "veg"
      );
    }

    return list;
  };

  const safeSections = Array.isArray(burgerSections) ? burgerSections : [];
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
          sectionRefs.current[section.id];

        if (
          element &&
          scrollPosition >= element.offsetTop
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
  }, [activeFilter, visibleSections]);

  useEffect(() => {
    const handleVoiceUIAction = (event) => {
      const action = event.detail?.action;
      if (action === "filter_veg") {
        setActiveFilter("veg");
      } else if (action === "filter_non_veg") {
        setActiveFilter("non veg");
      } else if (action === "filter_both") {
        setActiveFilter("both");
      }
    };

    window.addEventListener("kiosk-ui-action", handleVoiceUIAction);
    return () => window.removeEventListener("kiosk-ui-action", handleVoiceUIAction);
  }, []);

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
        <SpotlightShelf
          category="burger"
          activeFilter={activeFilter}
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

export default Burgermenu;
