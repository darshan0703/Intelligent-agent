import io
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from kokoro import KPipeline
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
)
from state import conversation_context, reset_conversation


load_dotenv()


print("INITIALIZING KOKORO TTS...")

tts_pipeline = KPipeline(
    lang_code="a"
)

print("KOKORO TTS READY")


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5175"
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


@app.get("/menu/burgers")
def burgers():
    return get_menu("burger")


@app.get("/menu/drinks")
def drinks():
    return get_menu("drink")


@app.get("/menu/sides")
def sides():
    return get_menu("side")


@app.get("/menu/desserts")
def desserts():
    return get_menu("dessert")


@app.get("/cart")
def cart():
    return get_cart()


@app.post("/message")
def message(request: MessageRequest):
    print("USER MESSAGE:", request.message)

    response = process_message(
        request.message,
        llm,
    )

    if isinstance(response, KioskResponse):
        return response.model_dump()

    return {
        "screen": None,
        "message": response,
        "cart": conversation_context.get("cart", []),
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

@app.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...)
):
    whisper_cli = os.path.expanduser(
        "~/whisper.cpp/build/bin/whisper-cli"
    )

    whisper_model = os.path.expanduser(
        "~/whisper.cpp/models/ggml-small.en.bin"
    )

    ffmpeg = "/opt/homebrew/bin/ffmpeg"

    print("\n" + "=" * 80)
    print("STT REQUEST")
    print("=" * 80)

    print(
        "WHISPER CLI:",
        whisper_cli,
    )

    print(
        "WHISPER MODEL:",
        whisper_model,
    )

    print(
        "FFMPEG:",
        ffmpeg,
    )

    print(
        "UPLOADED FILE:",
        file.filename,
    )

    print(
        "CONTENT TYPE:",
        file.content_type,
    )

    if not Path(whisper_cli).exists():
        print("ERROR: Whisper CLI not found.")

        return {
            "success": False,
            "message": "Whisper CLI not found.",
        }

    if not Path(whisper_model).exists():
        print("ERROR: Whisper model not found.")

        return {
            "success": False,
            "message": "Whisper model not found.",
        }

    if not Path(ffmpeg).exists():
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

            input_file.write_bytes(
                audio_data
            )

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
                print(
                    "FFMPEG ERROR:"
                )

                print(
                    ffmpeg_result.stderr
                )

                return {
                    "success": False,
                    "message": "Audio conversion failed.",
                }

            print(
                "WAV CREATED:",
                wav_file.exists(),
            )

            if wav_file.exists():
                print(
                    "WAV SIZE:",
                    wav_file.stat().st_size,
                    "bytes",
                )

            print(
                "STARTING WHISPER..."
            )

            whisper_result = subprocess.run(
                [
                    whisper_cli,
                    "-m",
                    whisper_model,
                    "-f",
                    str(wav_file),
                    "-l",
                    "en",
                    "-nt",
                    "-np",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            print(
                "WHISPER FINISHED:",
                whisper_result.returncode,
            )

            if whisper_result.stderr:
                print(
                    "WHISPER STDERR:"
                )

                print(
                    whisper_result.stderr
                )

            if whisper_result.returncode != 0:
                print(
                    "WHISPER ERROR"
                )

                return {
                    "success": False,
                    "message": "Speech recognition failed.",
                }

            transcript = (
                whisper_result.stdout
                .strip()
            )

            print(
                "WHISPER TRANSCRIPT:",
                transcript,
            )

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