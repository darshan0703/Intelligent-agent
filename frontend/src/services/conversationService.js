import { sendMessage } from "./api.js";
import { waitForLatestScreenSync } from "./screenService.js";

export async function processCustomerMessage(message, options = {}) {
  try {
    console.log("CUSTOMER MESSAGE:", message);

    await waitForLatestScreenSync();

    const data = await sendMessage(message, options);

    console.log("BACKEND RESPONSE:", data);

    return data;

  } catch (error) {
    console.error(
      "Failed to process customer message:",
      error
    );

    throw error;
  }
}