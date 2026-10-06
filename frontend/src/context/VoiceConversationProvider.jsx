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

import {
  processCustomerMessage,
} from "../services/conversationService";

import {
  handleKioskResponse,
} from "../services/responseHandler";


const VoiceConversationContext =
  createContext(null);


export function VoiceConversationProvider({
  children,
}) {

  const navigate = useNavigate();


  const {
    setRecommendationData,
    setProductData,
  } = useKiosk();


  const {
    executeUIAction,
  } = useUIAction();


  const [
    voiceEnabled,
    setVoiceEnabled,
  ] = useState(false);


  // ====================================================
  // VOICE SESSION STATE
  // ====================================================

  const voiceEnabledRef =
    useRef(false);


  // Prevent multiple messages from being
  // processed at the same time.
  const processingRef =
    useRef(false);


  // ====================================================
  // LISTEN FOR CUSTOMER
  // ====================================================

  const listenForCustomer =
    useCallback(() => {

      if (
        !voiceEnabledRef.current ||
        processingRef.current
      ) {
        return;
      }


      console.log(
        "STARTING CUSTOMER LISTENING"
      );


      startListening(
        async (transcript) => {

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


            // Send the customer message through
            // the existing conversation pipeline.

            const data =
              await processCustomerMessage(
                transcript
              );


            console.log(
              "VOICE BACKEND RESPONSE:",
              data
            );


            // Apply the normal kiosk UI response.

            handleKioskResponse(
              data,
              {
                navigate,
                setRecommendationData,
                setProductData,
                executeUIAction,
              }
            );


            // =================================================
            // NORMAL KOKORO RESPONSE
            // =================================================
            //
            // IMPORTANT:
            //
            // Keep using the original speak().
            //
            // This is the existing working interruption
            // mechanism that you said already works.
            //

            if (data?.message) {

              speak(
                data.message,
                () => {

                  processingRef.current =
                    false;


                  if (
                    voiceEnabledRef.current
                  ) {

                    listenForCustomer();

                  }

                }
              );

            } else {

              processingRef.current =
                false;


              if (
                voiceEnabledRef.current
              ) {

                listenForCustomer();

              }

            }


          } catch (error) {

            console.error(
              "VOICE MESSAGE ERROR:",
              error
            );


            processingRef.current =
              false;


            if (
              voiceEnabledRef.current
            ) {

              listenForCustomer();

            }

          }

        }
      );

    }, [
      navigate,
      setRecommendationData,
      setProductData,
      executeUIAction,
    ]);


  // ====================================================
  // BARGE-IN / INTERRUPTION
  // ====================================================
  //
  // THIS IS YOUR EXISTING INTERRUPTION FLOW.
  //
  // Do not change the logic here.
  // ====================================================

  useEffect(() => {

    setInterruptionHandler(() => {

      if (
        !voiceEnabledRef.current
      ) {
        return;
      }


      console.log(
        "CUSTOMER TOOK THE TURN"
      );


      // The previous response is no longer
      // relevant after customer interruption.

      processingRef.current =
        false;


      // Start listening for the new customer question.

      listenForCustomer();

    });


    return () => {

      setInterruptionHandler(
        null
      );

    };

  }, [
    listenForCustomer
  ]);


  // ====================================================
  // START VOICE CONVERSATION
  // ====================================================

  const startVoiceConversation =
    useCallback(
      async () => {

        if (
          voiceEnabledRef.current
        ) {
          return;
        }


        voiceEnabledRef.current =
          true;


        processingRef.current =
          false;


        setVoiceEnabled(true);


        console.log(
          "VOICE INTERFACE ENABLED"
        );


        try {

          // =================================================
          // PREPARE MICROPHONE BEFORE INITIAL GREETING
          // =================================================
          //
          // This is the ONLY additional preparation needed
          // for the initial greeting.
          //
          // It does NOT create a new interruption system.
          //
          // The greeting still uses the normal speak().
          //

          await prepareVoiceInput();


          if (
            !voiceEnabledRef.current
          ) {
            return;
          }


          // =================================================
          // INITIAL GREETING
          // =================================================

          speak(
            "Hi! Welcome to Burger King. What can I get for you today?",
            () => {

              if (
                voiceEnabledRef.current
              ) {

                listenForCustomer();

              }

            }
          );


        } catch (error) {

          console.error(
            "FAILED TO START VOICE GREETING:",
            error
          );


          voiceEnabledRef.current =
            false;


          processingRef.current =
            false;


          setVoiceEnabled(false);

        }

      },
      [
        listenForCustomer,
      ]
    );


  // ====================================================
  // STOP VOICE CONVERSATION
  // ====================================================

  const stopVoiceConversation =
    useCallback(() => {

      voiceEnabledRef.current =
        false;


      processingRef.current =
        false;


      stopListening();


      setVoiceEnabled(false);


      console.log(
        "VOICE INTERFACE DISABLED"
      );

    }, []);


  // ====================================================
  // PROVIDER
  // ====================================================

  return (

    <VoiceConversationContext.Provider
      value={{
        voiceActive:
          voiceEnabled,

        startVoiceConversation,

        stopVoiceConversation,
      }}
    >

      {children}

    </VoiceConversationContext.Provider>

  );

}


// ======================================================
// HOOK
// ======================================================

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