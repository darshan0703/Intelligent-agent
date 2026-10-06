import io
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from services.cashier_agent import run_cashier_agent
import json
import numpy as np
import soundfile as sf
try:
    import whisper
except Exception:
    whisper = None
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
try:
    from kokoro import KPipeline
except Exception:
    KPipeline = None
from langchain_groq import ChatGroq
from pydantic import BaseModel
from kiosk_service import process_message
from schemas import KioskResponse
from screen_controls import get_screen_controls
from services.cart_service import (
    add_item as cart_add_item,
    add_meal,
    clear_cart,
    complete_order,
    get_cart,
    update_cart_item,
)
from services.meal_service import get_meal_options
from services.menu_service import (
    add_item,
    get_available,
    get_category,
    get_menu,
    get_product,
)
from services.productservice import get_product_recommendations
from state import conversation_context, reset_conversation
load_dotenv()
print("INITIALIZING KOKORO TTS...")
try:
    if KPipeline is not None:
        tts_pipeline = KPipeline(
            lang_code="a"
        )
        print("KOKORO TTS READY")
    else:
        tts_pipeline = None
        print("KOKORO TTS NOT LOADED")
except Exception as e:
    tts_pipeline = None
    print("KOKORO TTS INIT FAILED:", repr(e))
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
)
class MessageRequest(BaseModel):
    message: str
class AddToCartRequest(BaseModel):
    item_name: str
    quantity: int = 1
@app.get("/health")
def health():
    return {
        "status": "running"
    }
@app.post("/session/start")
def start_session():
    session_id = str(uuid.uuid4())
    reset_conversation(session_id)
    print("SESSION STARTED")
    print(conversation_context)
    return {
        "success": True,
        "session_id": session_id,
        "message": "Welcome to Burger King",
        "voice_enabled": True,
    }
@app.post("/screen")
def update_screen(request: dict):
    screen = request.get("screen")
    if not screen:
        return {
            "success": False,
            "message": "screen is required",
        }
    conversation_context["current_screen"] = screen
    conversation_context["available_controls"] = (
        get_screen_controls(screen)
    )
    print("SCREEN SYNC:", screen)
    print(
        "AVAILABLE CONTROLS:",
        conversation_context["available_controls"],
    )
    return {
        "success": True,
        "screen": screen,
        "available_controls": (
            conversation_context["available_controls"]
        ),
    }
@app.post("/session/preference")
def set_preference(request: dict):
    preference = request.get("preference")
    if preference:
        normalized = preference.lower().replace("-", " ").replace("_", " ").strip()
        conversation_context["food_preference"] = normalized
    return {
        "success": True,
        "food_preference": conversation_context.get("food_preference")
    }
@app.get("/menu/burgers")
def burgers(preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    return get_menu("burger", preference=pref)
@app.get("/menu/drinks")
def drinks(preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    return get_menu("drink", preference=pref)
@app.get("/menu/sides")
def sides(preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    return get_menu("side", preference=pref)
@app.get("/menu/desserts")
def desserts(preference: str | None = None):
    pref = preference or conversation_context.get("food_preference")
    return get_menu("dessert", preference=pref)
@app.get("/cart")
def cart():
    return get_cart()


@app.get("/product/{item_name}/recommendations")
@app.get("/menu/product/{item_name}/recommendations")
def product_recommendations(item_name: str, preference: str | None = None):
    product = get_product(item_name)
    if not product:
        return {"recommendations": []}
    cart = conversation_context.get("cart", [])
    pref = preference or conversation_context.get("food_preference")
    recs = get_product_recommendations(product, cart=cart, preference=pref)
    return {"recommendations": recs}


@app.post("/product/recommendations")
@app.post("/menu/product/recommendations")
def product_recommendations_post(request: dict):
    item_name = request.get("item_name")
    if not item_name:
        return {"recommendations": []}
    product = get_product(item_name)
    if not product:
        return {"recommendations": []}
    cart = request.get("cart") if request.get("cart") is not None else conversation_context.get("cart", [])
    pref = request.get("preference") or conversation_context.get("food_preference")
    recs = get_product_recommendations(product, cart=cart, preference=pref)
    return {"recommendations": recs}


@app.post("/message")
def message(request: MessageRequest):
    print("USER MESSAGE:", request.message)
    # Clear any response left by a previous agent turn.
    conversation_context.pop(
        "_last_kiosk_response",
        None,
    )
    # ==========================================================
    # FAST-PATH FOR DIRECT CATEGORY REQUESTS
    # ==========================================================
    # Avoid an unnecessary LLM round trip for simple, unambiguous
    # category requests while keeping the existing KioskResponse
    # and backend category/recommendation pipeline.
    msg_clean = request.message.strip().lower()
    cat_map = {
        "i want a burger": "burger",
        "i want burger": "burger",
        "burger": "burger",
        "burgers": "burger",
        "i want a drink": "drink",
        "i want drink": "drink",
        "drink": "drink",
        "drinks": "drink",
        "i want a side": "side",
        "i want side": "side",
        "i want sides": "side",
        "side": "side",
        "sides": "side",
        "i want a dessert": "dessert",
        "i want dessert": "dessert",
        "dessert": "dessert",
        "desserts": "dessert",
    }
    if msg_clean in cat_map:
        from services.menuservice import handle_category
        target_cat = cat_map[msg_clean]
        kiosk_response = handle_category(target_cat, conversation_context)
        if kiosk_response is not None:
            conversation_context["current_screen"] = kiosk_response.screen
            return kiosk_response.model_dump()
    # ==========================================================
    # CASHIER AGENT (with resilient error handling)
    # ==========================================================
    try:
        agent_response = run_cashier_agent(
            request.message,
            conversation_context,
        )
    except Exception as e:
        print(f"Agent execution error (falling back to processor): {e}")
        agent_response = None
    # ==========================================================
    # CHECK WHETHER THE AGENT PERFORMED A KIOSK ACTION
    # ==========================================================
    kiosk_response = conversation_context.pop(
        "_last_kiosk_response",
        None,
    )
    if kiosk_response is not None:
        kiosk_response.message = agent_response
        frontend_response = kiosk_response.model_dump()
        return frontend_response
    # ==========================================================
    # AGENT-ONLY CONVERSATION
    # ==========================================================
    #
    # The agent may handle a request conversationally without
    # performing a kiosk action. In that case there is no
    # _last_kiosk_response, but the agent response is still valid.
    #
    # Do NOT send the same request to the legacy system, otherwise
    # the old intent router can execute an unintended action.
    # ==========================================================
    if agent_response and agent_response.strip():
        return {
            "screen": conversation_context.get("current_screen"),
            "message": agent_response,
            "cart": conversation_context.get(
                "cart",
                [],
            ),
        }
    # ==========================================================
    # OLD SYSTEM FALLBACK
    # ==========================================================
    #
    # Only fall back when the new agent genuinely produced no
    # response. This allows capabilities to be migrated gradually.
    # ==========================================================
    response = process_message(
        request.message,
        llm,
    )
    if isinstance(response, KioskResponse):
        return response.model_dump()
    return {
        "screen": None,
        "message": response,
        "cart": conversation_context.get(
            "cart",
            [],
        ),
    }
@app.post("/cart/add")
def cart_add(request: AddToCartRequest):
    return cart_add_item(
        request.item_name,
        request.quantity,
    )
@app.post("/cart/clear")
def cart_clear():
    return clear_cart()
@app.post("/meal/options")
def meal_options(request: dict):
    item_id = request.get("item_id")
    if item_id is None:
        return {
            "success": False,
            "message": "item_id is required",
        }
    meal_flow = conversation_context.get(
        "meal_flow"
    )
    if (
        meal_flow
        and meal_flow.get("item_id") == item_id
        and meal_flow.get("status") == "declined"
    ):
        return {
            "success": True,
            "is_meal_available": False,
            "message": "Meal offer was declined.",
        }
    offer = get_meal_options(item_id)
    if not offer:
        return {
            "success": False,
            "message": "Meal not available.",
        }
    conversation_context["meal_flow"] = {
        "item_id": item_id,
        "status": "pending",
    }
    return offer
@app.post("/meal/decline")
def decline_meal():
    meal_flow = conversation_context.get(
        "meal_flow"
    )
    if not meal_flow:
        return {
            "success": False,
            "message": "No active meal flow.",
        }
    meal_flow["status"] = "declined"
    return {
        "success": True,
        "meal_flow": meal_flow,
    }
@app.post("/cart/add-meal")
def cart_add_meal(request: dict):
    return add_meal(
        request["meal"],
        request.get("quantity", 1),
    )
@app.patch("/cart/item")
def update_cart_item_endpoint(request: dict):
    return update_cart_item(
        request.get("item_index"),
        request.get("action"),
    )
@app.post("/order/complete")
def complete_order_endpoint():
    result = complete_order(
        conversation_context.get("cart", [])
    )
    return result
# ============================================================
# LOCAL KOKORO TEXT TO SPEECH
# ============================================================
@app.post("/tts")
def text_to_speech(request: dict):
    text = request.get("text")
    print("TTS REQUEST:", text)
    if not text:
        return Response(
            content=b"",
            media_type="audio/wav",
            status_code=400,
        )
    try:
        print("GENERATING KOKORO AUDIO...")
        generator = tts_pipeline(
            text,
            voice="af_heart",
        )
        audio_segments = []
        for _, _, audio in generator:
            audio_segments.append(
                np.asarray(audio)
            )
        if not audio_segments:
            raise RuntimeError(
                "Kokoro generated no audio."
            )
        audio_data = np.concatenate(
            audio_segments
        )
        audio_buffer = io.BytesIO()
        sf.write(
            audio_buffer,
            audio_data,
            24000,
            format="WAV",
        )
        audio_buffer.seek(0)
        audio_bytes = audio_buffer.read()
        print(
            "KOKORO AUDIO GENERATED:",
            len(audio_bytes),
            "bytes",
        )
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
        )
    except Exception as e:
        print(
            "KOKORO TTS ERROR:",
            repr(e),
        )
        return Response(
            content=b"TTS generation failed",
            media_type="text/plain",
            status_code=500,
        )
# ============================================================
# LOCAL WHISPER SPEECH TO TEXT
# ============================================================
print("INITIALIZING WHISPER STT...")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "small.en")
try:
    if whisper is not None:
        whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
        print(f"WHISPER STT READY: {WHISPER_MODEL_NAME}")
    else:
        whisper_model = None
        print("WHISPER STT NOT INSTALLED")
except Exception as e:
    whisper_model = None
    print("WHISPER INITIALIZATION ERROR:", repr(e))
@app.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
):
    print("\n" + "=" * 80)
    print("STT REQUEST")
    print("=" * 80)
    # Find FFmpeg automatically so the same code works on
    # macOS, Linux/Codespaces, and other environments.
    ffmpeg = shutil.which("ffmpeg")
    print("WHISPER MODEL:", WHISPER_MODEL_NAME)
    print("FFMPEG:", ffmpeg)
    print("UPLOADED FILE:", file.filename)
    print("CONTENT TYPE:", file.content_type)
    if whisper_model is None:
        print("ERROR: Whisper model is not initialized.")
        return {
            "success": False,
            "message": "Whisper model is not initialized.",
        }
    if not ffmpeg:
        print("ERROR: FFmpeg not found.")
        return {
            "success": False,
            "message": "FFmpeg not found.",
        }
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            input_file = temp_dir / "input.webm"
            wav_file = temp_dir / "input.wav"
            print("READING UPLOADED AUDIO...")
            audio_data = await file.read()
            print(
                "AUDIO SIZE:",
                len(audio_data),
                "bytes",
            )
            if not audio_data:
                return {
                    "success": False,
                    "message": "Uploaded audio file is empty.",
                }
            input_file.write_bytes(audio_data)
            # --------------------------------------------------------
            # Convert browser WebM/Opus audio to 16 kHz mono WAV.
            # --------------------------------------------------------
            print("STARTING FFMPEG...")
            ffmpeg_result = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(input_file),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(wav_file),
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            print(
                "FFMPEG FINISHED:",
                ffmpeg_result.returncode,
            )
            if ffmpeg_result.returncode != 0:
                print("FFMPEG ERROR:")
                print(ffmpeg_result.stderr)
                return {
                    "success": False,
                    "message": "Audio conversion failed.",
                }
            print("WAV CREATED:", wav_file.exists())
            if not wav_file.exists():
                return {
                    "success": False,
                    "message": "WAV file was not created.",
                }
            print(
                "WAV SIZE:",
                wav_file.stat().st_size,
                "bytes",
            )
            # --------------------------------------------------------
            # Transcribe using the installed openai-whisper package.
            # This replaces the old whisper.cpp CLI dependency.
            # --------------------------------------------------------
            print("STARTING WHISPER...")
            whisper_result = whisper_model.transcribe(
                str(wav_file),
                language="en",
                fp16=False,
            )
            transcript = whisper_result.get("text", "").strip()
            print("WHISPER TRANSCRIPT:", transcript)
            print("=" * 80 + "\n")
            return {
                "success": True,
                "text": transcript,
            }
    except subprocess.TimeoutExpired as e:
        print(
            "STT TIMEOUT:",
            repr(e),
        )
        return {
            "success": False,
            "message": "Speech recognition timed out.",
        }
    except Exception as e:
        print(
            "STT ERROR:",
            repr(e),
        )
        return {
            "success": False,
            "message": "Speech recognition failed.",
        }
