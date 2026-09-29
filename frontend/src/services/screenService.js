const API_URL =
  "https://miniature-waffle-4j95794qwjqxfj677-8000.app.github.dev";

export async function syncScreen(screen) {
  console.log("SYNCING CURRENT SCREEN:", screen);

  try {
    const response = await fetch(`${API_URL}/screen`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        screen,
      }),
    });

    console.log("SCREEN SYNC STATUS:", response.status);

    if (!response.ok) {
      throw new Error(`Screen sync failed: ${response.status}`);
    }

    const data = await response.json();

    console.log("SCREEN SYNC SUCCESS:", data);

    return data;
  } catch (error) {
    console.error("SCREEN SYNC ERROR:", error);
    throw error;
  }
}