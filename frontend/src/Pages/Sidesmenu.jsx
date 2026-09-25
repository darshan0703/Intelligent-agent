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

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

function Sidesmenu() {
  const location = useLocation();
  const { foodPreference, setFoodPreference } = useKiosk();

  const [activeFilter, setActiveFilter] = useState(() => {
    const stored = sessionStorage.getItem("dietary_preference");
    const loc = location.state?.activeFilter;
    const pref = loc || foodPreference || stored || "both";
    return pref === "non_veg" ? "non veg" : pref;
  });

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (foodPreference) {
      const p = foodPreference === "non_veg" ? "non veg" : foodPreference;
      setActiveFilter(p);
    }
  }, [foodPreference]);

  const [sidesSections, setSidesSections] = useState([]);

  useEffect(() => {
    setLoading(true);
    const isFiltered = activeFilter && activeFilter !== "both";
    const queryParam = isFiltered ? `?preference=${encodeURIComponent(activeFilter)}` : "";
    fetch(`${API_BASE_URL}/menu/sides${queryParam}`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setSidesSections(data);
        }
      })
      .catch((err) => console.warn("Failed to fetch sides menu:", err))
      .finally(() => setLoading(false));
  }, [activeFilter]);

  const menuContentRef = useRef(null);

  useEffect(() => {
    if (menuContentRef.current) {
      menuContentRef.current.scrollTop = 0;
    }
  }, [activeFilter]);

  const sectionRefs = useRef({});

  const [activeCategory, setActiveCategory] = useState("");

  const handleFilterChange = (f) => {
    const norm = f === "non_veg" ? "non veg" : f;
    setActiveFilter(norm);
    if (setFoodPreference) setFoodPreference(norm);
  };

  const [quickFilter, setQuickFilter] = useState("all");

  const filterProducts = (products) => {
    if (!products || !Array.isArray(products)) {
      return [];
    }

    let list = products;
    const norm = (activeFilter || "both").trim().toLowerCase();
    if (norm === "veg") {
      list = list.filter(product => {
        const ft = String(product.type || product.foodType || product.food_type || "").toLowerCase();
        return ft === "veg" || (!ft.includes("non") && !/chicken|wings|nugget/i.test(product.name || ""));
      });
    } else if (norm === "non veg" || norm === "non_veg") {
      list = list.filter(product => {
        const ft = String(product.type || product.foodType || product.food_type || "").toLowerCase();
        return ft.includes("non") || /chicken|wings|nugget/i.test(product.name || "");
      });
    }

    if (quickFilter === "bestseller") {
      list = list.filter(
        p => (p.badge && p.badge.toLowerCase().includes("bestseller")) || /fries|nuggets|rings|wings/i.test(p.name)
      );
    } else if (quickFilter === "value") {
      list = list.filter(
        p => Number(p.price) <= 99 || (p.badge && p.badge.toLowerCase().includes("value"))
      );
    } else if (quickFilter === "spicy") {
      list = list.filter(
        p => (p.badge && /spicy|heat/i.test(p.badge)) || /peri|spicy|fiery|chilli/i.test(p.name)
      );
    } else if (quickFilter === "veg") {
      list = list.filter(
        p => {
          const ft = String(p.type || p.foodType || p.food_type || "").toLowerCase();
          return ft === "veg" || (!ft.includes("non") && !/chicken|wings|nugget/i.test(p.name || ""));
        }
      );
    }

    return list;
  };

  const safeSections = Array.isArray(sidesSections) ? sidesSections : [];
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

  }, [activeFilter,sidesSections]);

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

  }, [activeFilter,sidesSections]);

  return (

    <div className="menu-page">

      <Header title="Choose Your Sides" />

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
          category="side"
          activeFilter={activeFilter}
          activeQuickFilter={quickFilter}
          onQuickFilterSelect={(f) => setQuickFilter(prev => prev === f ? "all" : f)}
        />

        {loading ? (
          <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--bk-brown)" }}>
            <span style={{ fontSize: "36px" }}>⏳</span>
            <p style={{ fontFamily: "Flame", fontSize: "20px", marginTop: "12px" }}>Loading delicious sides...</p>
          </div>
        ) : visibleSections.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 20px", color: "var(--bk-brown)" }}>
            <span style={{ fontSize: "36px" }}>🌿</span>
            <p style={{ fontFamily: "Flame", fontSize: "22px", marginTop: "12px" }}>No {activeFilter} sides found</p>
            <p style={{ fontSize: "14px", opacity: 0.8 }}>Try switching filters above to see more choices</p>
          </div>
        ) : (
          visibleSections.map(section => (
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
          ))
        )}

      </div>

      <CartContainer />

    </div>

  );

}

export default Sidesmenu;
