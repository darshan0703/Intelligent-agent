import { sendMessage } from "./api";

export async function processCustomerMessage(message) {
  try {
    console.log("CUSTOMER MESSAGE:", message);

    const data = await sendMessage(message);

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