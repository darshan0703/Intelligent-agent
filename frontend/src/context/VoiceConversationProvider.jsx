import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import { useNavigate } from "react-router-dom";

import { useKiosk } from "./KioskContext";
import { useUIAction } from "./UIActionContext";

import {
  startListening,
  stopListening,
  speak,
  setInterruptionHandler,
} from "../services/voice/voiceService";

import { processCustomerMessage } from "../services/conversationService";
import { handleKioskResponse } from "../services/responseHandler";

const VoiceConversationContext = createContext(null);

export function VoiceConversationProvider({ children }) {
  const navigate = useNavigate();

  const {
    setRecommendationData,
    setProductData,
  } = useKiosk();

  const {
    executeUIAction,
  } = useUIAction();

  const [voiceEnabled, setVoiceEnabled] = useState(false);

  // True for the entire voice interaction.
  // It represents the voice interface being enabled,
  // NOT an individual browser recognition session.
  const voiceEnabledRef = useRef(false);

  // Prevent multiple customer messages from being
  // processed at the same time.
  const processingRef = useRef(false);

  const listenForCustomer = useCallback(() => {
    if (
      !voiceEnabledRef.current ||
      processingRef.current
    ) {
      return;
    }

    console.log("STARTING CUSTOMER LISTENING");

    startListening(async (transcript) => {
      if (
        !voiceEnabledRef.current ||
        processingRef.current
      ) {
        return;
      }

      processingRef.current = true;

      try {
        console.log(
          "VOICE TRANSCRIPT:",
          transcript
        );

        // Stop the current recording/listening cycle.
        stopListening();

        // Send the same customer message through
        // the normal TheAtom conversation pipeline.
        const data =
          await processCustomerMessage(
            transcript
          );

        console.log(
          "VOICE BACKEND RESPONSE:",
          data
        );

        // Apply exactly the same screen/UI response
        // used by the rest of the kiosk.
        handleKioskResponse(
          data,
          {
            navigate,
            setRecommendationData,
            setProductData,
            executeUIAction,
          }
        );

        // Speak the backend's response.
        if (data?.message) {
          speak(
            data.message,
            () => {
              processingRef.current = false;

              // Continue the same voice interaction.
              // This does NOT create a new transaction.
              if (voiceEnabledRef.current) {
                listenForCustomer();
              }
            }
          );
        } else {
          processingRef.current = false;

          if (voiceEnabledRef.current) {
            listenForCustomer();
          }
        }
      } catch (error) {
        console.error(
          "VOICE MESSAGE ERROR:",
          error
        );

        processingRef.current = false;

        if (voiceEnabledRef.current) {
          listenForCustomer();
        }
      }
    });
  }, [
    navigate,
    setRecommendationData,
    setProductData,
    executeUIAction,
  ]);

  /*
   * Barge-in:
   *
   * voiceService detects the customer speaking while
   * the kiosk is talking. It stops TTS and calls this.
   */
  useEffect(() => {
    setInterruptionHandler(() => {
      if (!voiceEnabledRef.current) {
        return;
      }

      console.log(
        "CUSTOMER TOOK THE TURN"
      );

      // The previous cashier response is no longer
      // relevant once the customer interrupts.
      processingRef.current = false;

      listenForCustomer();
    });

    return () => {
      setInterruptionHandler(null);
    };
  }, [listenForCustomer]);

  const startVoiceConversation =
    useCallback(() => {
      if (voiceEnabledRef.current) {
        return;
      }

      voiceEnabledRef.current = true;
      processingRef.current = false;

      setVoiceEnabled(true);

      console.log(
        "VOICE INTERFACE ENABLED"
      );

      // Initial cashier greeting.
      speak(
        "Hi! Welcome to Burger King. What can I get for you today?",
        () => {
          if (voiceEnabledRef.current) {
            listenForCustomer();
          }
        }
      );
    }, [listenForCustomer]);

  const stopVoiceConversation =
    useCallback(() => {
      voiceEnabledRef.current = false;
      processingRef.current = false;

      stopListening();

      setVoiceEnabled(false);

      console.log(
        "VOICE INTERFACE DISABLED"
      );
    }, []);

  return (
    <VoiceConversationContext.Provider
      value={{
        voiceActive: voiceEnabled,
        startVoiceConversation,
        stopVoiceConversation,
      }}
    >
      {children}
    </VoiceConversationContext.Provider>
  );
}

export function useVoiceConversation() {
  const context =
    useContext(
      VoiceConversationContext
    );

  if (!context) {
    throw new Error(
      "useVoiceConversation must be used inside VoiceConversationProvider"
    );
  }

  return context;
}