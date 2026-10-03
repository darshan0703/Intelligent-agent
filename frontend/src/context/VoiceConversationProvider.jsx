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

  /*
   * Voice interface enabled.
   */
  const [voiceEnabled, setVoiceEnabled] = useState(false);

  /*
   * Current voice state:
   *
   * idle
   * listening
   * speaking
   * processing
   */
  const [voiceStatus, setVoiceStatus] = useState("idle");

  /*
   * Keep voice state accessible outside React renders.
   */
  const voiceEnabledRef = useRef(false);

  /*
   * Prevent multiple customer requests.
   */
  const processingRef = useRef(false);

  /*
   * --------------------------------------------------
   * HANDLE CUSTOMER TRANSCRIPT
   * --------------------------------------------------
   */
  const handleCustomerTranscript = useCallback(
    async (transcript) => {
      if (!voiceEnabledRef.current) {
        return;
      }

      if (processingRef.current) {
        return;
      }

      console.log(
        "CUSTOMER TRANSCRIPT RECEIVED:",
        transcript
      );

      /*
       * Customer has finished speaking.
       *
       * Now we are processing the question.
       */
      processingRef.current = true;

      setVoiceStatus("processing");

      try {
        /*
         * Send transcript to your existing
         * conversation backend.
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
         * Apply kiosk UI response.
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
         * If backend returned a message,
         * speak it using Kokoro.
         */
        if (data?.message) {

          console.log(
            "KOKORO ANSWER:",
            data.message
          );

          setVoiceStatus("speaking");

          speak(
            data.message,
            () => {

              /*
               * Kokoro finished.
               *
               * Now show Listening.
               */
              processingRef.current = false;

              if (
                voiceEnabledRef.current
              ) {
                setVoiceStatus(
                  "listening"
                );

                startListening(
                  handleCustomerTranscript
                );
              }
            }
          );

        } else {

          /*
           * No response message.
           */
          processingRef.current = false;

          if (
            voiceEnabledRef.current
          ) {
            setVoiceStatus(
              "listening"
            );

            startListening(
              handleCustomerTranscript
            );
          }
        }

      } catch (error) {

        console.error(
          "VOICE MESSAGE ERROR:",
          error
        );

        processingRef.current = false;

        if (
          voiceEnabledRef.current
        ) {
          setVoiceStatus(
            "listening"
          );

          startListening(
            handleCustomerTranscript
          );
        }
      }
    },
    [
      navigate,
      setRecommendationData,
      setProductData,
      executeUIAction,
    ]
  );

  /*
   * --------------------------------------------------
   * BARGE-IN HANDLER
   * --------------------------------------------------
   *
   * This is called when the customer speaks while
   * Kokoro is speaking.
   */
  useEffect(() => {

    setInterruptionHandler(() => {

      if (!voiceEnabledRef.current) {
        return;
      }

      console.log(
        "CUSTOMER INTERRUPTED KOKORO"
      );

      /*
       * IMPORTANT:
       *
       * voiceService has already stopped Kokoro.
       *
       * The microphone and recorder are still active.
       *
       * We only change the UI here.
       */
      setVoiceStatus("listening");

    });

    return () => {
      setInterruptionHandler(null);
    };

  }, []);

  /*
   * --------------------------------------------------
   * START VOICE CONVERSATION
   * --------------------------------------------------
   *
   * IMPORTANT:
   *
   * 1. Start microphone + recorder + VAD.
   * 2. Start Kokoro greeting.
   *
   * Both are active at the same time.
   */
  const startVoiceConversation =
    useCallback(
      async () => {

        if (voiceEnabledRef.current) {
          return;
        }

        /*
         * Enable voice interface.
         */
        voiceEnabledRef.current = true;

        processingRef.current = false;

        setVoiceEnabled(true);

        console.log(
          "VOICE INTERFACE ENABLED"
        );

        try {

          /*
           * ---------------------------------------
           * STEP 1
           * Start microphone + VAD + recorder.
           * ---------------------------------------
           */
          console.log(
            "STARTING MICROPHONE AND VAD"
          );

          await startListening(
            handleCustomerTranscript
          );

          if (
            !voiceEnabledRef.current
          ) {
            return;
          }

          /*
           * ---------------------------------------
           * STEP 2
           * Start initial Kokoro greeting.
           * ---------------------------------------
           */
          console.log(
            "STARTING INITIAL KOKORO GREETING"
          );

          setVoiceStatus("speaking");

          speak(
            "Hi! Welcome to Burger King. What can I get for you today?",
            () => {

              /*
               * Greeting finished normally.
               */
              if (
                voiceEnabledRef.current
              ) {

                console.log(
                  "INITIAL GREETING FINISHED"
                );

                setVoiceStatus(
                  "listening"
                );
              }
            }
          );

        } catch (error) {

          console.error(
            "VOICE START ERROR:",
            error
          );

          voiceEnabledRef.current = false;

          processingRef.current = false;

          setVoiceEnabled(false);

          setVoiceStatus("idle");
        }
      },
      [handleCustomerTranscript]
    );

  /*
   * --------------------------------------------------
   * STOP VOICE CONVERSATION
   * --------------------------------------------------
   */
  const stopVoiceConversation =
    useCallback(() => {

      console.log(
        "STOPPING VOICE INTERFACE"
      );

      voiceEnabledRef.current = false;

      processingRef.current = false;

      stopListening();

      setVoiceEnabled(false);

      setVoiceStatus("idle");

      console.log(
        "VOICE INTERFACE DISABLED"
      );

    }, []);

  /*
   * --------------------------------------------------
   * CONTEXT
   * --------------------------------------------------
   */
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