import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  startListening,
  stopListening,
  stopVoiceSession,
  speak,
  setInterruptionHandler,
} from "../services/voice/voiceService";

import {
  sendMessage,
} from "../services/conversationService";

import {
  handleKioskResponse,
} from "../services/responseHandler";


const VoiceConversationContext =
  createContext(null);


export function VoiceConversationProvider({
  children,
}) {

  const [isVoiceActive, setIsVoiceActive] =
    useState(false);

  const [isProcessing, setIsProcessing] =
    useState(false);

  const [recommendationData, setRecommendationData] =
    useState(null);

  const [productData, setProductData] =
    useState(null);


  const navigateRef =
    useRef(null);

  const processingRef =
    useRef(false);

  const activeRef =
    useRef(false);


  /*
   * =======================================================
   * HANDLE CUSTOMER TRANSCRIPT
   * =======================================================
   */

  const handleTranscript = async (
    transcript
  ) => {

    if (!transcript) {
      return;
    }


    if (!activeRef.current) {
      return;
    }


    if (processingRef.current) {

      console.log(
        "VOICE PROCESSING ALREADY IN PROGRESS"
      );

      return;
    }


    console.log(
      "================================="
    );

    console.log(
      "VOICE TRANSCRIPT:",
      transcript
    );

    console.log(
      "================================="
    );


    processingRef.current = true;

    setIsProcessing(true);


    try {

      /*
       * Stop current customer listening.
       */

      stopListening();


      console.log(
        "SENDING CUSTOMER MESSAGE..."
      );


      /*
       * Send transcript to backend.
       */

      const response =
        await sendMessage(
          transcript
        );


      console.log(
        "VOICE BACKEND RESPONSE:",
        response
      );


      /*
       * Handle:
       * - screen navigation
       * - recommendations
       * - product data
       * - UI actions
       */

      handleKioskResponse(
        response,
        {
          navigate:
            navigateRef.current,

          setRecommendationData,

          setProductData,

          executeUIAction:
            undefined,
        }
      );


      /*
       * Speak backend response.
       */

      if (
        response?.message &&
        activeRef.current
      ) {

        speak(
          response.message,
          async () => {

            /*
             * Kokoro finished.
             *
             * Start listening for
             * the next customer request.
             */

            if (
              activeRef.current
            ) {

              console.log(
                "TTS FINISHED - STARTING CUSTOMER LISTENING"
              );


              await startListening(
                handleTranscript
              );

            }

          }
        );

      } else {

        /*
         * If backend has no message,
         * immediately start listening again.
         */

        if (activeRef.current) {

          await startListening(
            handleTranscript
          );

        }

      }


    } catch (error) {

      console.error(
        "VOICE CONVERSATION ERROR:",
        error
      );


      /*
       * Error response.
       */

      if (activeRef.current) {

        speak(
          "Sorry, I could not process that. Please try again.",
          async () => {

            if (activeRef.current) {

              await startListening(
                handleTranscript
              );

            }

          }
        );

      }

    } finally {

      processingRef.current = false;

      setIsProcessing(false);

    }

  };


  /*
   * =======================================================
   * START VOICE CONVERSATION
   * =======================================================
   */

  const startVoiceConversation =
    async () => {

      if (activeRef.current) {

        console.log(
          "VOICE CONVERSATION ALREADY ACTIVE"
        );

        return;
      }


      console.log(
        "================================="
      );

      console.log(
        "STARTING VOICE CONVERSATION"
      );

      console.log(
        "================================="
      );


      activeRef.current = true;

      setIsVoiceActive(true);


      /*
       * Start microphone + Silero
       * BEFORE Kokoro greeting.
       *
       * This allows barge-in.
       */

      console.log(
        "STARTING CUSTOMER LISTENER BEFORE GREETING"
      );


      try {

        await startListening(
          handleTranscript
        );


        console.log(
          "CUSTOMER LISTENER READY"
        );


        /*
         * Start initial greeting.
         */

        console.log(
          "STARTING INITIAL GREETING"
        );


        speak(
          "Welcome to Burger King. How can I help you today?",
          async () => {

            /*
             * When greeting finishes,
             * make sure customer listening
             * is active.
             */

            if (
              activeRef.current
            ) {

              console.log(
                "GREETING FINISHED - CUSTOMER LISTENING"
              );


              await startListening(
                handleTranscript
              );

            }

          }
        );


      } catch (error) {

        console.error(
          "VOICE START ERROR:",
          error
        );


        activeRef.current = false;

        setIsVoiceActive(false);

      }

    };


  /*
   * =======================================================
   * STOP VOICE CONVERSATION
   * =======================================================
   */

  const stopVoiceConversation =
    () => {

      console.log(
        "STOPPING VOICE CONVERSATION"
      );


      activeRef.current = false;

      processingRef.current = false;


      setIsVoiceActive(false);

      setIsProcessing(false);


      stopVoiceSession();

    };


  /*
   * =======================================================
   * BARGE-IN HANDLER
   * =======================================================
   *
   * Called when customer speaks while
   * Kokoro is speaking.
   * =======================================================
   */

  useEffect(() => {

    setInterruptionHandler(
      async () => {

        if (!activeRef.current) {
          return;
        }


        console.log(
          "================================="
        );

        console.log(
          "CUSTOMER INTERRUPTED GREETING / TTS"
        );

        console.log(
          "STOPPING TTS AND LISTENING TO CUSTOMER"
        );

        console.log(
          "================================="
        );


        /*
         * voiceService stops Kokoro
         * before calling this handler.
         *
         * Now start customer listening.
         */

        if (
          !processingRef.current
        ) {

          await startListening(
            handleTranscript
          );

        }

      }
    );

  }, []);


  /*
   * =======================================================
   * CLEANUP
   * =======================================================
   */

  useEffect(() => {

    return () => {

      activeRef.current = false;

      processingRef.current = false;

      stopVoiceSession();

    };

  }, []);


  /*
   * =======================================================
   * CONTEXT VALUE
   * =======================================================
   */

  const value = {

    isVoiceActive,

    isProcessing,

    recommendationData,

    setRecommendationData,

    productData,

    setProductData,

    startVoiceConversation,

    stopVoiceConversation,

    navigateRef,

  };


  return (
    <VoiceConversationContext.Provider
      value={value}
    >
      {children}
    </VoiceConversationContext.Provider>
  );

}


/*
 * =======================================================
 * HOOK
 * =======================================================
 */

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


export default VoiceConversationProvider;