const API_URL = "http://127.0.0.1:8000";


export async function syncScreen(screen) {

  try {

    console.log(
      "SYNCING CURRENT SCREEN:",
      screen
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