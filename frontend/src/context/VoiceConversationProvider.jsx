import {
  createContext,
  useContext,
  useState,
} from "react";

import { useNavigate } from "react-router-dom";

import { useKiosk } from "./KioskContext";
import { useUIAction } from "./UIActionContext";

import {
  startListening,
  stopListening,
  speak,
} from "../services/voiceService";

import {
  processCustomerMessage,
} from "../services/conversationService";

import {
  handleKioskResponse,
} from "../services/responseHandler";


const VoiceConversationContext =
  createContext();


export function VoiceConversationProvider({
  children
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
    voiceActive,
    setVoiceActive
  ] = useState(false);


  // ==========================================
  // START VOICE CONVERSATION
  // ==========================================

  const startVoiceConversation = () => {

    if (voiceActive) return;

    setVoiceActive(true);


    startListening(
      async (transcript) => {

        try {

          console.log(
            "VOICE TRANSCRIPT:",
            transcript
          );


          // ==========================================
          // SEND CUSTOMER MESSAGE TO BACKEND
          // ==========================================

          const data =
            await processCustomerMessage(
              transcript
            );


          console.log(
            "VOICE BACKEND RESPONSE:",
            data
          );


          // ==========================================
          // SPEAK BACK TO CUSTOMER
          // ==========================================

          if (data?.message) {

            speak(data.message);

          }


          // ==========================================
          // EXECUTE UI ACTION
          // ==========================================

          handleKioskResponse(
            data,
            {
              navigate,
              setRecommendationData,
              setProductData,
              executeUIAction,
            }
          );


        } catch (error) {

          console.error(
            "VOICE MESSAGE ERROR:",
            error
          );

        }

      }
    );

  };


  // ==========================================
  // STOP VOICE CONVERSATION
  // ==========================================

  const stopVoiceConversation = () => {

    stopListening();

    setVoiceActive(false);

  };


  // ==========================================
  // PROVIDER
  // ==========================================

  return (

    <VoiceConversationContext.Provider
      value={{

        voiceActive,

        startVoiceConversation,

        stopVoiceConversation,

      }}
    >

      {children}

    </VoiceConversationContext.Provider>

  );

}


export function useVoiceConversation() {

  return useContext(
    VoiceConversationContext
  );

}