import React, { useEffect, useState } from "react";
import "./SpotlightShelf.css";
import { useCart } from "../context/CartContext";
import { useKiosk } from "../context/KioskContext";
import { useNavigate, useLocation } from "react-router-dom";
import { getRoute } from "../utils/navigation";
import { getSessionId } from "../utils/session";

const API_BASE_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== "undefined" && process.env?.REACT_APP_API_BASE_URL) ||
  "http://127.0.0.1:8000";

export default function SpotlightShelf({ category = "burger", activeFilter = "both", onQuickFilterSelect, activeQuickFilter = "all" }) {
  const [spotlightItems, setSpotlightItems] = useState([]);
  const [headline, setHeadline] = useState("Curated For You");
  const [subline, setSubline] = useState("Hand-picked favorites to complete your meal");
  const [circadianBadge, setCircadianBadge] = useState("⭐ Chef's Picks");
  const [manifestationNudge, setManifestationNudge] = useState("");

  const { addItemOptimistic, itemCount, winbackOffer, clearWinbackOffer } = useCart();
  const { setProductData } = useKiosk();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const sid = getSessionId();
    const isFiltered = activeFilter && activeFilter !== "both";
    const prefParam = isFiltered ? `&preference=${encodeURIComponent(activeFilter)}` : "";
    fetch(`${API_BASE_URL}/menu/spotlight/${category}?session_id=${sid}${prefParam}`)
      .then((res) => res.json())
      .then((data) => {
        if (data && data.success && Array.isArray(data.spotlight)) {
          setSpotlightItems(data.spotlight);
          if (data.headline) setHeadline(data.headline);
          if (data.subline) setSubline(data.subline);
          if (data.circadian_badge) setCircadianBadge(data.circadian_badge);
          if (data.manifestation_nudge) setManifestationNudge(data.manifestation_nudge);
        }
      })
      .catch((err) => console.warn("Spotlight fetch error:", err));
  }, [category, itemCount, activeFilter]);

  const displayedItems = (() => {
    if (activeFilter === "veg") {
      return spotlightItems.filter(item => (item.food_type || item.type || item.foodType) === "veg");
    }
    if (activeFilter === "non veg" || activeFilter === "non_veg") {
      return spotlightItems.filter(item => {
        const t = (item.food_type || item.type || item.foodType || "").toLowerCase();
        return t.includes("non");
      });
    }
    return spotlightItems; // "both" or cleared
  })();

  if (!displayedItems || displayedItems.length === 0) {
    return null;
  }

  const handleCardClick = (product) => {
    setProductData({
      screen: "product",
      data: {
        product,
        recommendations: [],
      },
    });
    navigate(getRoute("product"), {
      state: {
        origin: location.pathname,
      },
    });
  };

  const handleAddClick = (e, product) => {
    e.stopPropagation();
    if (product.is_meal_available) {
      handleCardClick(product);
    } else {
      addItemOptimistic(product, 1);
    }
  };

  const chips = [
    { id: "all", label: "All Items" },
    { id: "bestseller", label: "🔥 Bestsellers" },
    { id: "value", label: "⭐ Value Under ₹99" },
    { id: "spicy", label: "🌶️ Spicy Hot" },
    { id: "veg", label: "🌿 Pure Veg" },
  ];

  return (
    <div className="spotlight-container">
      {/* OBSESSION WINBACK BANNER (IF CUSTOMER DELETED AN ITEM) */}
      {winbackOffer?.winback_item && (
        <div className="spotlight-winback-banner">
          <div className="winback-left">
            <span className="winback-flame">🔥</span>
            <div>
              <div className="winback-title-line">
                <span className="winback-tag">Obsession Pick</span>
                <span className="winback-removed-note">
                  Missed out on {winbackOffer.removed_item?.name}?
                </span>
              </div>
              <p className="winback-pitch">{winbackOffer.winback_item.pitch}</p>
            </div>
          </div>
          <div className="winback-right">
            <span className="winback-price">₹{winbackOffer.winback_item.price}</span>
            <button
              className="winback-add-btn"
              onClick={() => {
                addItemOptimistic(winbackOffer.winback_item, 1);
                clearWinbackOffer();
              }}
            >
              + Add
            </button>
            <button className="winback-close-btn" onClick={clearWinbackOffer} title="Dismiss">
              ✕
            </button>
          </div>
        </div>
      )}

      {/* HEADER */}
      <div className="spotlight-header">
        <div className="spotlight-title-group">
          <span className="spotlight-sparkle-icon">✨</span>
          <div>
            <h3 className="spotlight-headline">{headline}</h3>
            <p className="spotlight-subline">{subline}</p>
          </div>
        </div>
        <span className="spotlight-ai-badge">{circadianBadge}</span>
      </div>

      {/* MANIFESTATION NUDGE / SOCIAL PROOF HOOK */}
      {manifestationNudge && (
        <div className="spotlight-manifestation-nudge">
          <span className="manifestation-spark">⚡</span>
          <span className="manifestation-text">{manifestationNudge}</span>
        </div>
      )}

      {/* CARDS CAROUSEL */}
      <div className="spotlight-cards-strip">
        {displayedItems.map((item) => (
          <div
            key={item.id}
            className={`spotlight-item-card ${item.has_micro_deal ? "has-micro-deal" : ""}`}
            onClick={() => handleCardClick(item)}
          >
            {item.badge && (
              <span className="spotlight-item-badge">
                {item.badge}
              </span>
            )}
            {item.deal_tag && (
              <span className="spotlight-deal-pill">
                {item.deal_tag}
              </span>
            )}
            <div className="spotlight-img-wrap">
              <img src={item.image} alt={item.name} className="spotlight-img" />
            </div>
            <div className="spotlight-card-content">
              <span className="spotlight-item-name">{item.name}</span>
              {item.synergy_reason && (
                <span className="spotlight-item-reason">{item.synergy_reason}</span>
              )}
              <div className="spotlight-card-footer">
                {item.has_micro_deal ? (
                  <div className="spotlight-price-bundle">
                    <span className="spotlight-item-price offer">₹{item.offer_price}</span>
                    <span className="spotlight-orig-price">₹{item.original_price}</span>
                    <span className="spotlight-discount-tag">-{item.discount_pct}%</span>
                  </div>
                ) : (
                  <span className="spotlight-item-price">₹{item.price}</span>
                )}
                <button
                  className={`spotlight-add-btn ${item.has_micro_deal ? "deal-btn" : ""}`}
                  onClick={(e) => handleAddClick(e, item)}
                >
                  {item.has_micro_deal ? "+ Add Deal" : "+ Add"}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* QUICK FILTER CHIPS */}
      <div className="spotlight-chips-row">
        {chips.map((chip) => (
          <button
            key={chip.id}
            className={`spotlight-chip-btn ${activeQuickFilter === chip.id ? "active" : ""}`}
            onClick={() => onQuickFilterSelect && onQuickFilterSelect(chip.id)}
          >
            {chip.label}
          </button>
        ))}
      </div>
    </div>
  );
}
