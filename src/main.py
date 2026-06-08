# ============================================================
#  VOICE-ENABLED INTELLIGENT ROBOTIC SYSTEM (Google-Powered)
#  Now with a Siri-style animated blob interface
# ============================================================

# ---- Imports ----
import speech_recognition as sr
import webbrowser
import requests
import os
import tempfile
import time
import math
import threading
import pygame
from elevenlabs.client import ElevenLabs
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
# ---- User personalization ----
USER_NAME = "Doreen"



# Load secrets from .env file
load_dotenv()

# ---- API Keys (loaded from .env) ----
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")
WEATHER_API_KEY     = os.getenv("WEATHER_API_KEY")
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY")

# Safety check — fail loudly if a key is missing
if not all([GEMINI_API_KEY, WEATHER_API_KEY, ELEVENLABS_API_KEY]):
    raise RuntimeError(
        "Missing API key in .env file. "
        "Make sure .env exists and contains GEMINI_API_KEY, "
        "WEATHER_API_KEY, and ELEVENLABS_API_KEY."
    )

GEMINI_MODEL = "gemini-2.5-flash-lite"
# ---- Voice settings ----
ELEVEN_VOICE_ID = "WildqLEK65ZWlow6dqtw"                  # Bella — warm female
ELEVEN_MODEL    = "eleven_flash_v2_5" 

# ---- GUI settings ----
WINDOW_W, WINDOW_H = 600, 700
FPS = 60

# ---- Initialise clients ----
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Initialise pygame (do this BEFORE pygame.mixer for cleanest startup)
pygame.init()
pygame.mixer.init()


# ============================================================
#  SHARED STATE — read by GUI thread, written by assistant thread
# ============================================================
class AssistantState:
    def __init__(self):
        self.mode = "idle"           # idle | listening | thinking | speaking
        self.user_text = ""          # what the user said
        self.assistant_text = (
            f"Hi {USER_NAME}! How can I help you today?"
        )
        self.running = True          # main loop control

state = AssistantState()
gemini_call_count = 0


# ============================================================
#  speak() — ElevenLabs ultra-natural voice
# ============================================================
def speak(text):
    print("Assistant:", text)
    state.assistant_text = text
    state.mode = "speaking"
    try:
        audio_stream = eleven_client.text_to_speech.convert(
            voice_id=ELEVEN_VOICE_ID,
            model_id=ELEVEN_MODEL,
            text=text,
            output_format="mp3_44100_128",
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tmp_path = fp.name
            for chunk in audio_stream:
                if chunk:
                    fp.write(chunk)
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy() and state.running:
            pygame.time.wait(50)
        pygame.mixer.music.unload()
        os.remove(tmp_path)
    except Exception as e:
        print(f"TTS error: {e}")


# ============================================================
#  listen() — Captures mic audio and transcribes
# ============================================================
def listen():
    state.mode = "listening"
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=8)
        except sr.WaitTimeoutError:
            state.mode = "idle"
            return ""
    state.mode = "thinking"
    try:
        query = r.recognize_google(audio)
        print("You said:", query)
        state.user_text = query
        return query.lower()
    except sr.UnknownValueError:
        speak("Sorry, I did not catch that.")
        return ""
    except sr.RequestError:
        speak("Speech service is unreachable.")
        return ""


# ============================================================
#  ask_gemini() — Gemini Flash-Lite with Google Search grounding
# ============================================================
def ask_gemini(query):
    global gemini_call_count
    gemini_call_count += 1
    print(f"[Gemini call #{gemini_call_count}]")
    try:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            system_instruction=(
                f"You are a friendly voice assistant talking to {USER_NAME}. "
                "Answer in 2 to 3 short, natural sentences. "
                "No bullet points, no markdown, no lists, no asterisks. "
                "Just plain spoken English suitable for a text-to-speech engine."
            ),
        )
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL, contents=query, config=config,
        )
        if response.text:
            return response.text.strip()
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    text_parts = [p.text for p in candidate.content.parts
                                  if hasattr(p, 'text') and p.text]
                    if text_parts:
                        return " ".join(text_parts).strip()
        return None
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "quota" in error_str:
            print(f"Gemini quota error: {e}")
            return "QUOTA_HIT"
        elif "api key" in error_str or "401" in error_str or "403" in error_str:
            print(f"Gemini auth error: {e}")
            return "AUTH_ERROR"
        else:
            print(f"Gemini error: {e}")
        return None


# ============================================================
#  get_weather() — Live weather
# ============================================================
def get_weather(city):
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric"}
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if str(data.get("cod")) != "200":
            return None
        description = data["weather"][0]["description"]
        temperature = data["main"]["temp"]
        humidity    = data["main"]["humidity"]
        feels_like  = data["main"]["feels_like"]
        return (f"The weather in {city} is currently {description}. "
                f"The temperature is {temperature:.0f} degrees Celsius, "
                f"feels like {feels_like:.0f}, with humidity at {humidity} percent.")
    except Exception:
        return None


# ============================================================
#  answer() — Routes the query
# ============================================================
def answer(query):
    if not query:
        return False

    # Weather
    if "weather" in query or "temperature" in query or "forecast" in query:
        if " in " in query:
            city = query.split(" in ")[-1].strip().rstrip("?.! ")
        else:
            speak("Which city would you like the weather for?")
            city_query = listen()
            if not city_query:
                return False
            city = city_query.strip().rstrip("?.! ")
        report = get_weather(city)
        if report:
            speak(report)
        else:
            speak(f"Sorry, I could not find the weather for {city}.")
        return True

    # Gemini
    gemini_answer = ask_gemini(query)
    if gemini_answer == "QUOTA_HIT":
        speak("I have reached my daily question limit. "
              "The limit will reset in a few hours, please try again later.")
        return True
    if gemini_answer == "AUTH_ERROR":
        speak("There is a problem with my connection. Please check the API key.")
        return True
    if gemini_answer:
        speak(gemini_answer)
        return True

    # Last resort
    try:
        speak("Let me open Google for you.")
        webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
        return True
    except Exception:
        speak("Sorry, I could not find anything.")
        return False


# ============================================================
#  get_greeting() — Time-aware
# ============================================================
def get_greeting():
    hour = time.localtime().tm_hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


# ============================================================
#  ASSISTANT THREAD — runs the listen/answer loop
# ============================================================
def assistant_loop():
    greeting = get_greeting()
    speak(f"Hi {USER_NAME}! {greeting}. How can I help you today?")

    while state.running:
        state.mode = "idle"
        q = listen()

        if not state.running:
            break

        if any(word in q for word in ["stop", "exit", "quit", "goodbye", "bye"]):
            speak(f"Goodbye {USER_NAME}! Have a great day.")
            state.running = False
            break

        answered = answer(q)

        if answered and state.running:
            state.mode = "idle"
            time.sleep(2)
            if state.running:
                speak("Is there anything more you would like to know?")


# ============================================================
#  GUI — the wobbly glowing Siri-style blob
# ============================================================

# Color palettes for each state (R, G, B)
PALETTES = {
    "idle":      {"core": (80, 140, 220),  "glow": (60, 120, 200),  "wobble": 0.04, "speed": 0.018, "pulse": 0.10},
    "listening": {"core": (120, 220, 255), "glow": (80, 200, 255),  "wobble": 0.10, "speed": 0.040, "pulse": 0.30},
    "thinking":  {"core": (180, 120, 240), "glow": (140, 80, 220),  "wobble": 0.12, "speed": 0.060, "pulse": 0.20},
    "speaking":  {"core": (255, 180, 140), "glow": (240, 120, 100), "wobble": 0.08, "speed": 0.050, "pulse": 0.35},
}

# Smooth color interpolation between current and target state
def lerp_color(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def lerp(a, b, t):
    return a + (b - a) * t


def wrap_text(text, font, max_width):
    """Break text into lines that fit within max_width pixels."""
    words = text.split(" ")
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def run_gui():
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(f"{USER_NAME}'s Voice Assistant")
    clock = pygame.time.Clock()

    # Fonts
    font_label = pygame.font.SysFont("Segoe UI", 14)
    font_user = pygame.font.SysFont("Segoe UI", 18)
    font_assistant = pygame.font.SysFont("Segoe UI", 22, bold=False)
    font_state = pygame.font.SysFont("Segoe UI", 13, italic=True)

    # Animation state
    t = 0
    current_palette = {
        "core": list(PALETTES["idle"]["core"]),
        "glow": list(PALETTES["idle"]["glow"]),
        "wobble": PALETTES["idle"]["wobble"],
        "speed": PALETTES["idle"]["speed"],
        "pulse": PALETTES["idle"]["pulse"],
    }

    blob_cx, blob_cy = WINDOW_W // 2, 220
    base_radius = 80

    while state.running:
        # ---- Handle window events ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                state.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                state.running = False

        # ---- Smoothly interpolate toward the target palette ----
        target = PALETTES[state.mode]
        smooth = 0.08   # how fast colors morph (0.0 = frozen, 1.0 = instant)
        current_palette["core"] = list(lerp_color(current_palette["core"], target["core"], smooth))
        current_palette["glow"] = list(lerp_color(current_palette["glow"], target["glow"], smooth))
        current_palette["wobble"] = lerp(current_palette["wobble"], target["wobble"], smooth)
        current_palette["speed"]  = lerp(current_palette["speed"],  target["speed"],  smooth)
        current_palette["pulse"]  = lerp(current_palette["pulse"],  target["pulse"],  smooth)

        t += 1

        # ---- Draw background ----
        screen.fill((10, 10, 20))   # very dark navy

        # ---- Calculate blob breathing ----
        pulse = 1 + math.sin(t * current_palette["speed"]) * current_palette["pulse"]
        radius = base_radius * pulse

        # ---- Draw glow layers (soft outer halo) ----
        for i in range(8, 0, -1):
            r = radius + i * 12
            alpha = int(255 * 0.05 * (i / 8))
            glow_surf = pygame.Surface((int(r * 2 + 4), int(r * 2 + 4)), pygame.SRCALPHA)
            pygame.draw.circle(
                glow_surf,
                (*current_palette["glow"], alpha),
                (int(r + 2), int(r + 2)),
                int(r),
            )
            screen.blit(glow_surf, (blob_cx - r - 2, blob_cy - r - 2))

        # ---- Draw the wobbly blob shape ----
        points = []
        num_points = 80
        for i in range(num_points + 1):
            ang = (i / num_points) * math.pi * 2
            wobble = (
                math.sin(ang * 3 + t * current_palette["speed"] * 2.0) * current_palette["wobble"] +
                math.sin(ang * 5 - t * current_palette["speed"] * 1.4) * current_palette["wobble"] * 0.6 +
                math.sin(ang * 2 + t * current_palette["speed"] * 0.8) * current_palette["wobble"] * 0.4
            )
            r = radius * (1 + wobble)
            x = blob_cx + math.cos(ang) * r
            y = blob_cy + math.sin(ang) * r
            points.append((x, y))
        pygame.draw.polygon(screen, current_palette["core"], points)

        # ---- Inner highlight (gives a 3D feel) ----
        highlight_surf = pygame.Surface((int(radius * 2), int(radius * 2)), pygame.SRCALPHA)
        pygame.draw.circle(
            highlight_surf,
            (255, 255, 255, 40),
            (int(radius * 0.75), int(radius * 0.70)),
            int(radius * 0.45),
        )
        screen.blit(highlight_surf, (blob_cx - radius, blob_cy - radius))

        # ---- Draw current state label below blob ----
        state_label_map = {
            "idle":      "Ready — say something...",
            "listening": "Listening...",
            "thinking":  "Thinking...",
            "speaking":  "Speaking...",
        }
        label_surf = font_state.render(state_label_map[state.mode], True, (180, 180, 200))
        screen.blit(label_surf, (WINDOW_W // 2 - label_surf.get_width() // 2, 360))

        # ---- Draw the user's question ----
        if state.user_text:
            you_label = font_label.render("You:", True, (130, 150, 180))
            screen.blit(you_label, (40, 410))
            user_lines = wrap_text(state.user_text, font_user, WINDOW_W - 80)
            for i, line in enumerate(user_lines[:2]):    # max 2 lines
                line_surf = font_user.render(line, True, (200, 210, 220))
                screen.blit(line_surf, (40, 432 + i * 26))

        # ---- Draw the assistant's reply ----
        if state.assistant_text:
            asst_label = font_label.render("Assistant:", True, (180, 160, 130))
            screen.blit(asst_label, (40, 510))
            asst_lines = wrap_text(state.assistant_text, font_assistant, WINDOW_W - 80)
            for i, line in enumerate(asst_lines[:5]):    # max 5 lines
                line_surf = font_assistant.render(line, True, (255, 255, 255))
                screen.blit(line_surf, (40, 535 + i * 30))

        # ---- Hint at bottom ----
        hint = font_label.render(
            "Say 'goodbye' to exit  •  Press Esc to close window",
            True, (90, 90, 110),
        )
        screen.blit(hint, (WINDOW_W // 2 - hint.get_width() // 2, WINDOW_H - 30))

        pygame.display.flip()
        clock.tick(FPS)

    # Stop any audio still playing, then close
    pygame.mixer.music.stop()
    pygame.quit()


# ============================================================
#  MAIN — start the assistant in a thread, run GUI on main
# ============================================================
if __name__ == "__main__":
    # daemon=True means the thread dies automatically when the main thread exits
    assistant_thread = threading.Thread(target=assistant_loop, daemon=True)
    assistant_thread.start()

    # GUI runs on the main thread (required by pygame on macOS / Windows)
    run_gui()
