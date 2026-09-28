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

  const voiceEnabledRef = useRef(false);

  const processingRef = useRef(false);

  // Prevent multiple listening sessions
  const listeningRef = useRef(false);

  /*
   * Start listening for the customer.
   */
  const listenForCustomer = useCallback(() => {
    if (!voiceEnabledRef.current) {
      return;
    }

    if (processingRef.current) {
      return;
    }

    if (listeningRef.current) {
      return;
    }

    console.log("STARTING CUSTOMER LISTENING");

    listeningRef.current = true;

    startListening(async (transcript) => {
      listeningRef.current = false;

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

        /*
         * Stop microphone listening for this turn.
         */
        stopListening();

        /*
         * Send customer message to backend.
         */
        const data =
          await processCustomerMessage(
            transcript
          );

        console.log(
          "VOICE BACKEND RESPONSE:",
          data
        );

        /*
         * Update kiosk UI immediately.
         *
         * This happens before TTS playback.
         */
        handleKioskResponse(
          data,
          {
            navigate,
            setRecommendationData,
            setProductData,
            executeUIAction,
          }
        );

        /*
         * Speak backend response.
         */
        if (data?.message) {
          speak(
            data.message,
            () => {
              processingRef.current = false;

              /*
               * Start listening again after
               * the cashier finishes speaking.
               */
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
   * BARGE-IN
   *
   * If the customer speaks while TTS is playing,
   * voiceService stops the TTS and calls this handler.
   */
  useEffect(() => {
    setInterruptionHandler(() => {
      if (!voiceEnabledRef.current) {
        return;
      }

      console.log(
        "CUSTOMER TOOK THE TURN"
      );

      /*
       * The previous cashier response
       * is no longer relevant.
       */
      processingRef.current = false;

      listeningRef.current = false;

      /*
       * Start listening immediately.
       */
      listenForCustomer();
    });

    return () => {
      setInterruptionHandler(null);
    };
  }, [listenForCustomer]);

  /*
   * START VOICE CONVERSATION
   */
  const startVoiceConversation =
    useCallback(() => {

      /*
       * Prevent duplicate initialization.
       */
      if (voiceEnabledRef.current) {
        console.log(
          "VOICE INTERFACE ALREADY ENABLED"
        );

        return;
      }

      voiceEnabledRef.current = true;
      processingRef.current = false;
      listeningRef.current = false;

      setVoiceEnabled(true);

      console.log(
        "VOICE INTERFACE ENABLED"
      );

      /*
       * IMPORTANT:
       *
       * Start listening BEFORE the welcome TTS finishes.
       *
       * This allows barge-in.
       */
      listenForCustomer();

      /*
       * Welcome message.
       *
       * We do NOT wait for this to finish
       * before starting the microphone.
       */
      speak(
        "Hi! Welcome to Burger King. What can I get for you today?"
      );

    }, [listenForCustomer]);

  /*
   * STOP VOICE CONVERSATION
   */
  const stopVoiceConversation =
    useCallback(() => {

      voiceEnabledRef.current = false;
      processingRef.current = false;
      listeningRef.current = false;

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