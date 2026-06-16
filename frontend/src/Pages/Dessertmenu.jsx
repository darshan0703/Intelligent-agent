import "./menu.css";

import Header from "../components/Header";
import BackButton from "../components/BackButton";
import Menusidebar from "../components/Menusidebar";
import CartContainer from "../components/CartContainer";
import MenuSection from "../components/MenuSection";

import {
  useRef,
  useState,
  useEffect
} from "react";

import { dessertSections } from "../data/desserts";

function Dessertmenu() {

  const menuContentRef = useRef(null);

  const sectionRefs = useRef({});

  const [activeCategory, setActiveCategory] =
    useState(
      dessertSections[0]?.title || ""
    );

  const categories = dessertSections.map(
    section => section.title
  );

  const scrollToCategory = (categoryTitle) => {

    setActiveCategory(categoryTitle);

    const section =
      dessertSections.find(
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
        dessertSections[0]?.title;

      dessertSections.forEach(section => {

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
          dessertSections[
            dessertSections.length - 1
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

  }, []);

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

        {dessertSections.map(
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

      <CartContainer
        itemCount={0}
        total={0}
      />

    </div>

  );

}

export default Dessertmenu;
