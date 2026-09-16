const BASE_URL = "http://127.0.0.1:8000";

// ---------- Session ----------

export async function startSession() {
  const response = await fetch(`${BASE_URL}/session/start`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to start session");
  }

  return response.json();
}

// ---------- Conversation ----------

export async function sendMessage(message) {
  const response = await fetch(`${BASE_URL}/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to send message");
  }

  return response.json();
}

// ---------- Menus ----------

export async function getBurgerMenu() {
  const response = await fetch(`${BASE_URL}/menu/burgers`);
  return response.json();
}

export async function getDrinkMenu() {
  const response = await fetch(`${BASE_URL}/menu/drinks`);
  return response.json();
}

export async function getSideMenu() {
  const response = await fetch(`${BASE_URL}/menu/sides`);
  return response.json();
}

export async function getDessertMenu() {
  const response = await fetch(`${BASE_URL}/menu/desserts`);
  return response.json();
}

// ---------- Cart ----------

export async function getCart() {
  const response = await fetch(`${BASE_URL}/cart`);
  return response.json();
}

export async function addToCart(item_name, quantity = 1) {
  const response = await fetch(`${BASE_URL}/cart/add`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      item_name,
      quantity,
    }),
  });

  return response.json();
}

export async function clearCart() {
  const response = await fetch(`${BASE_URL}/cart/clear`, {
    method: "POST",
  });

  return response.json();
}