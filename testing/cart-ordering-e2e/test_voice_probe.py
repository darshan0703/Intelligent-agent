import asyncio
import base64
import subprocess
from playwright.async_api import async_playwright

def generate_voice_wav(text: str) -> str:
    tmp_aiff = "/tmp/voice_probe.aiff"
    tmp_wav = "/tmp/voice_probe.wav"
    subprocess.run(["say", "-o", tmp_aiff, text], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", tmp_aiff, "-ar", "16000", "-ac", "1", tmp_wav], check=True, stderr=subprocess.DEVNULL)
    with open(tmp_wav, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

async def test_probe():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0]
        await context.grant_permissions(["microphone"], origin="http://localhost:5173")
        page = await context.new_page()

        await page.add_init_script("""
            window.__voiceAudioContext = null;
            window.__activeDestinations = [];

            navigator.mediaDevices.getUserMedia = async (constraints) => {
                if (!window.__voiceAudioContext) {
                    window.__voiceAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                }
                if (window.__voiceAudioContext.state === 'suspended') {
                    await window.__voiceAudioContext.resume();
                }
                const dest = window.__voiceAudioContext.createMediaStreamDestination();
                // Filter out closed destinations
                window.__activeDestinations = window.__activeDestinations.filter(d => 
                    d.stream.getAudioTracks().some(t => t.readyState === 'live')
                );
                window.__activeDestinations.push(dest);
                console.log("[TEST HOOK] Fresh getUserMedia destination created. Total active:", window.__activeDestinations.length);
                return dest.stream;
            };

            window.__speakVoice = async (base64Wav) => {
                console.log("[TEST HOOK] Speaking voice to all active destinations...");
                if (!window.__voiceAudioContext) {
                    window.__voiceAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                }
                if (window.__voiceAudioContext.state === 'suspended') {
                    await window.__voiceAudioContext.resume();
                }
                const binaryString = atob(base64Wav);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                const audioBuffer = await window.__voiceAudioContext.decodeAudioData(bytes.buffer.slice(0));
                
                const liveDests = window.__activeDestinations.filter(d => 
                    d.stream.getAudioTracks().some(t => t.readyState === 'live')
                );
                console.log("[TEST HOOK] Playing buffer to", liveDests.length, "live destinations");
                for (const dest of liveDests) {
                    const source = window.__voiceAudioContext.createBufferSource();
                    source.buffer = audioBuffer;
                    source.connect(dest);
                    source.start();
                }
                return audioBuffer.duration;
            };
        """)

        logs = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))

        print("Navigating to http://localhost:5173/...")
        await page.goto("http://localhost:5173/")
        await asyncio.sleep(2)

        touch_btn = page.locator(".touch-bar")
        if await touch_btn.is_visible():
            print("Clicking touch bar...")
            await touch_btn.click()
            print("Waiting for greeting TTS to finish and VAD to arm...")
            for _ in range(25):
                await asyncio.sleep(1)
                if any("SILERO LISTENING FOR CUSTOMER" in l for l in logs):
                    print("VAD is armed and listening!")
                    break

        # Wait a moment for audio pipeline stability
        await asyncio.sleep(2)
        print("Generating voice audio for: 'I want a bacon king'...")
        b64 = generate_voice_wav("I want a bacon king")
        print("Playing audio into microphone stream...")
        dur = await page.evaluate("window.__speakVoice", b64)
        print(f"Spoke voice command (duration {dur:.2f}s). Waiting for VAD detection and response...")

        for i in range(25):
            await asyncio.sleep(1)
            print(f"Wait {i+1}s... Current URL: {page.url}")
            for l in logs[-5:]:
                if "CUSTOMER" in l or "WHISPER" in l or "BACKEND" in l or "NAVIGAT" in l or "ERROR" in l:
                    print("  ->", l)
            if any("SCREEN SYNC RESPONSE" in l and "/Product" in page.url for l in logs):
                print("Navigated to product page!")
                break

        print("\n--- Summary logs ---")
        for l in logs:
            if any(k in l for k in ["SILERO", "WHISPER", "VOICE", "TRANSCRIPT", "CUSTOMER MESSAGE", "ERROR"]):
                print(l)

        await page.close()

if __name__ == "__main__":
    asyncio.run(test_probe())
