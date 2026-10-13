/**
 * Utility for safe, deterministic cart display ordering.
 * 
 * Rules:
 * 1. Newly added or quantity-increased items move to the bottom of the display order.
 * 2. Pure computation: No mutations to module state, React state, or sessionStorage during render.
 * 3. All items (including distinct line items with identical product names or customization attributes) are preserved.
 * 4. Authoritative cart, itemCount, and total are never altered.
 */

export const STORAGE_ORDER_KEY = "cart_item_order";
export const STORAGE_SNAPSHOT_KEY = "cart_qty_snapshot";

/**
 * Returns a stable base key for a cart item based on its identity.
 */
export const getCartItemBaseKey = (item) => {
  if (!item) return "unknown";
  if (item.type === "meal") {
    const mainId = item.main_item?.id || item.burger?.id || item.id || item.name || "";
    const sideId = item.side?.id || item.side?.name || "";
    const drinkId = item.drink?.id || item.drink?.name || "";
    return `meal_${mainId}_${sideId}_${drinkId}`;
  }
  return `item_${item.id || item.name || "unknown"}`;
};

/**
 * Maps cart items to entries with a unique key per line item, preserving duplicate lines.
 */
export const buildCartItemsWithKeys = (cart) => {
  if (!Array.isArray(cart)) return [];
  const counts = new Map();
  return cart.map((item, originalIndex) => {
    const baseKey = getCartItemBaseKey(item);
    const occurrence = counts.get(baseKey) || 0;
    counts.set(baseKey, occurrence + 1);
    const uniqueKey = `${baseKey}#${occurrence}`;
    return {
      ...item,
      _uniqueKey: uniqueKey,
      _originalIndex: originalIndex,
    };
  });
};

/**
 * Loads saved order keys from sessionStorage safely.
 */
export const loadSavedOrder = () => {
  try {
    const raw = sessionStorage.getItem(STORAGE_ORDER_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

/**
 * Saves order keys to sessionStorage safely.
 */
export const saveOrder = (order) => {
  try {
    sessionStorage.setItem(STORAGE_ORDER_KEY, JSON.stringify(order));
  } catch {
    // Ignore sessionStorage errors
  }
};

/**
 * Loads previous quantity snapshot from sessionStorage safely.
 */
export const loadSavedSnapshot = () => {
  try {
    const raw = sessionStorage.getItem(STORAGE_SNAPSHOT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
};

/**
 * Saves quantity snapshot to sessionStorage safely.
 */
export const saveSnapshot = (snapshot) => {
  try {
    sessionStorage.setItem(STORAGE_SNAPSHOT_KEY, JSON.stringify(snapshot));
  } catch {
    // Ignore sessionStorage errors
  }
};

/**
 * Resets saved cart ordering & snapshots from sessionStorage safely.
 */
export const resetCartOrder = () => {
  try {
    sessionStorage.removeItem(STORAGE_ORDER_KEY);
    sessionStorage.removeItem(STORAGE_SNAPSHOT_KEY);
  } catch {
    // Ignore sessionStorage errors
  }
};

/**
 * Pure function: Computes the ordered display list from cart, previous order, and previous snapshot.
 * Returns { displayCart, newOrder, newSnapshot }.
 * 
 * Quantity tracking is evaluated at the total baseKey level:
 * - A quantity increase triggers bottom-ordering only if the total count for that item increased.
 * - Deleting an item or decreasing quantity reduces total count, preventing false quantity-increase triggers.
 */
export const computeDisplayCart = (
  cart,
  savedOrder = loadSavedOrder(),
  prevSnapshot = loadSavedSnapshot()
) => {
  if (!cart || cart.length === 0) {
    return {
      displayCart: [],
      newOrder: [],
      newSnapshot: {},
    };
  }

  const itemsWithKeys = buildCartItemsWithKeys(cart);
  const currentKeysSet = new Set(itemsWithKeys.map((item) => item._uniqueKey));

  // Retain keys still in current cart
  let order = Array.isArray(savedOrder)
    ? savedOrder.filter((k) => currentKeysSet.has(k))
    : [];

  // Calculate current total quantities per baseKey
  const currentTotalQtyByBaseKey = new Map();
  for (const item of itemsWithKeys) {
    const baseKey = getCartItemBaseKey(item);
    const qty = Number(item.quantity) || 0;
    currentTotalQtyByBaseKey.set(
      baseKey,
      (currentTotalQtyByBaseKey.get(baseKey) || 0) + qty
    );
  }

  const prevSnapshotObj = prevSnapshot || {};

  // Check if any item's total quantity genuinely increased
  let updatedKey = null;
  if (Object.keys(prevSnapshotObj).length > 0) {
    for (const item of itemsWithKeys) {
      const baseKey = getCartItemBaseKey(item);
      const prevTotalQty = Number(prevSnapshotObj[baseKey]) || 0;
      const curTotalQty = currentTotalQtyByBaseKey.get(baseKey) || 0;

      // Only move to bottom if the overall quantity for this item increased
      if (curTotalQty > prevTotalQty && prevTotalQty > 0) {
        updatedKey = item._uniqueKey;
        break;
      }
    }
  }

  // If quantity increased, move that item to the end of the order
  if (updatedKey) {
    order = order.filter((k) => k !== updatedKey);
    order.push(updatedKey);
  }

  // Append any newly added keys not yet present in order
  for (const item of itemsWithKeys) {
    if (!order.includes(item._uniqueKey)) {
      order.push(item._uniqueKey);
    }
  }

  // Build ordered list preserving all item lines
  const itemMap = new Map();
  for (const item of itemsWithKeys) {
    itemMap.set(item._uniqueKey, item);
  }

  const displayCart = [];
  for (const k of order) {
    const item = itemMap.get(k);
    if (item) {
      displayCart.push(item);
    }
  }

  // Fallback: in case any item was missed, append it
  for (const item of itemsWithKeys) {
    if (!displayCart.some((d) => d._uniqueKey === item._uniqueKey)) {
      displayCart.push(item);
    }
  }

  // Build new snapshot tracking total quantity per baseKey
  const newSnapshot = {};
  for (const [baseKey, totalQty] of currentTotalQtyByBaseKey.entries()) {
    newSnapshot[baseKey] = totalQty;
  }

  return {
    displayCart,
    newOrder: order,
    newSnapshot,
  };
};
