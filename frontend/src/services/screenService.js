const API_URL = "";


export async function syncScreen(screen, extra = {}) {

  try {

    console.log(
      "SYNCING CURRENT SCREEN:",
      screen,
      extra
    );

    const response = await fetch(
      `${API_URL}/screen`,
      {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          screen,
          ...extra,
        }),
      }
    );


    if (!response.ok) {

      throw new Error(
        `Screen sync failed: ${response.status}`
      );

    }


    const data = await response.json();

    console.log(
      "SCREEN SYNC RESPONSE:",
      data
    );

    return data;

  } catch (error) {

    console.error(
      "SCREEN SYNC ERROR:",
      error
    );

  }
}