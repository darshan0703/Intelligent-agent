
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
  prepareVoiceInput,
  setInterruptionHandler,
} from "../services/voice/voiceService";

import { processCustomerMessage } from "../services/conversationService";
import { handleKioskResponse } from "../services/responseHandler";

const VoiceConversationContext = createContext(null);

export function VoiceConversationProvider({ children }) {
  const navigate = useNavigate();

  const { setRecommendationData, setProductData } = useKiosk();
  const { executeUIAction } = useUIAction();

  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("ready");

  const voiceEnabledRef = useRef(false);
  const processingRef = useRef(false);

  // Listen for a customer's request.
  const listenForCustomer = useCallback(() => {
    if (!voiceEnabledRef.current || processingRef.current) {
      return;
    }

    setVoiceStatus("listening");

    startListening(async (transcript) => {
      if (!voiceEnabledRef.current || processingRef.current) {
        return;
      }

      processingRef.current = true;
      setVoiceStatus("processing");

      try {
        stopListening();

        // Process the customer's request.
        const data = await processCustomerMessage(transcript);

        // Handle navigation, recommendations, products, and UI actions.
        handleKioskResponse(data, {
          navigate,
          setRecommendationData,
          setProductData,
          executeUIAction,
        });

        // Speak the generated response.
        if (data?.message) {
          speak(
            data.message,
            () => {
              processingRef.current = false;

              if (voiceEnabledRef.current) {
                listenForCustomer();
              } else {
                setVoiceStatus("ready");
              }
            },
            setVoiceStatus
          );
        } else {
          processingRef.current = false;
          setVoiceStatus("ready");

          if (voiceEnabledRef.current) {
            listenForCustomer();
          }
        }
      } catch (error) {
        console.error("VOICE MESSAGE ERROR:", error);

        processingRef.current = false;
        setVoiceStatus("ready");

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

  // Handle interruption when the customer starts speaking during TTS.
  useEffect(() => {
    setInterruptionHandler(() => {
      if (!voiceEnabledRef.current) {
        return;
      }

      processingRef.current = false;
      setVoiceStatus("listening");

      listenForCustomer();
    });

    return () => {
      setInterruptionHandler(null);
    };
  }, [listenForCustomer]);

  // Start the voice conversation and play the welcome message.
  const startVoiceConversation = useCallback(async () => {
    if (voiceEnabledRef.current) {
      return;
    }

    voiceEnabledRef.current = true;
    processingRef.current = false;

    setVoiceEnabled(true);
    setVoiceStatus("ready");

    try {
      await prepareVoiceInput();

      if (!voiceEnabledRef.current) {
        return;
      }

      speak(
        "Hi! Welcome to Burger King. What can I get for you today?",
        () => {
          if (voiceEnabledRef.current) {
            listenForCustomer();
          } else {
            setVoiceStatus("ready");
          }
        },
        setVoiceStatus
      );
    } catch (error) {
      console.error("FAILED TO START VOICE GREETING:", error);

      voiceEnabledRef.current = false;
      processingRef.current = false;

      setVoiceEnabled(false);
      setVoiceStatus("ready");
    }
  }, [listenForCustomer]);

  // Stop the voice conversation.
  const stopVoiceConversation = useCallback(() => {
    voiceEnabledRef.current = false;
    processingRef.current = false;

    stopListening();

    setVoiceEnabled(false);
    setVoiceStatus("ready");
  }, []);

  return (
    <VoiceConversationContext.Provider
      value={{
        voiceActive: voiceEnabled,
        voiceStatus,
        startVoiceConversation,
        stopVoiceConversation,
      }}
    >
      {children}
    </VoiceConversationContext.Provider>
  );
}

export function useVoiceConversation() {
  const context = useContext(VoiceConversationContext);

  if (!context) {
    throw new Error(
      "useVoiceConversation must be used inside VoiceConversationProvider"
    );
  }

  return context;
}
