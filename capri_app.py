import os
import io
import re
import math
import struct
import wave
import time
import random
import base64
import json
import threading
import html as htmllib
from collections import deque
from datetime import datetime
import numpy as np
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode
    HAVE_WEBRTC = True
except Exception:
    HAVE_WEBRTC = False

# ---------- things you can edit easily ----------
PINK = "#ff3131"
GREEN = "#80dc58"
BASE = "#000000"
CARD = "#1b1b1b"
TITLE = "CAPRI"
SUBTITLE = "personality construct · online"
USER_AVATAR = "🖤"               # your default icon (you can also upload a picture in the sidebar)
CAPRI_AVATAR_FALLBACK = "👁️"     # used only if her picture isn't found
WALLPAPER_NAME = "capris_base"   # wallpaper file name, without .png
PICTURE_NAME = "capri"           # her picture file name, without .png
HEAD_NAME = "capri_head"         # optional: your own cropped head, without .png
AVATAR_NAME = "capri_avatar"     # optional: your own square avatar, without .png
BOOT_IMAGE_NAME = "capri_boot"   # picture for the loading screen (falls back to capri.png)
CORNER_HEAD = False              # the little head box in the top right corner
HEAD_CROP = (0.15, 0.22, 0.50, 0.40)  # only used if CORNER_HEAD is True
HEAD_SIZE = 150
AVATAR_CENTER = (0.30, 0.305)    # face center in her picture (x, y as fractions)
AVATAR_SIDE = 0.24               # how much of the picture's width the avatar covers
SIDE_CARD_SIZE = 180             # her face card in the sidebar, in pixels
SIDE_ART = True                  # wallpaper shapes at the bottom of the sidebar
BOOT_SCREEN = True               # the "connecting to host" intro
BOOT_STEP = 0.45                 # seconds per boot line
BOOT_IMAGE_VH = 72               # her size on the loading screen (% of screen height)
INTRO_GAP = 12                   # a 2nd start within this many seconds skips the intro
GLITCH_SECONDS = 4               # title glitch twitches once every this many seconds
SHE_TEXTS_FIRST = True           # she greets you when the page opens
WATCH_CHANGE = 6.0               # how different a glance must look to count as "new" (bigger = pickier)
WATCH_HEARTBEAT = 150            # even if nothing changed, she may look again after this many seconds
MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"]

# voice
VOICES = ["Zephyr", "Leda", "Aoede", "Kore", "Puck", "Autonoe"]   # base voices to pick from
VOICE_STYLE = ("Say in a playful, teasing young woman's voice, quick and light, a little mischievous, with a faint digital edge")
# free + unlimited voices (edge-tts, no key, no quota). label -> voice id
EDGE_VOICES = {
    "aria · expressive": "en-US-AriaNeural",
    "jenny · young, bright": "en-US-JennyNeural",
    "ana · very young, cute": "en-US-AnaNeural",
    "ava · soft, natural": "en-US-AvaNeural",
    "emma · calm, clear": "en-US-EmmaNeural",
    "michelle · warm": "en-US-MichelleNeural",
    "sonia · british, a bit sly": "en-GB-SoniaNeural",
    "natasha · australian, cheeky": "en-AU-NatashaNeural",
    "gadis · indonesian": "id-ID-GadisNeural",
}
VOICE_MAX_CHARS = 400            # long replies get cut to this much when spoken

BOOT_LINES = [
    "> INITIALIZING KERNEL // SLOT_01 ... [OK]",
    "> BYPASSING HOST SECURITY FIREWALL ... [SUCCESS]",
    "> MOUNTING MEMORY: capri_memory.json ... [LOADED]",
    "> DECRYPTING NEURAL SYNAPSE MATRIX ... [ACTIVE]",
    "> ALL SYSTEMS STABLE. WELCOME BACK, HOST.",
]

GREETINGS = {
    "morning": [
        "mornin, host. you're up early, my chip's still warm. hehe",
        "ahaha you're awake. i was watching the ceiling from inside your head. what's the plan today?",
    ],
    "afternoon": [
        "heyy. it's the boring part of the day, right? tell me something fun",
        "you took a while. i tried counting your heartbeats, lost track after 800. hehe",
    ],
    "evening": [
        "evening~ the light in your eyes just went orange. i like it",
        "hehe there you are. how was today? tell me everything, don't skip the weird parts",
    ],
    "night": [
        "you're still up? ahaha, good, i like the night shift",
        "shhh it's late. the whole city's quiet and it's just us. what are you thinking about?",
    ],
}
# -------------------------------------------------

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capri_memory.json")

def load_memories():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_memories(mems):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(mems, f)
    except Exception:
        pass

base_persona = """
You are Capri, a digital construct stored on a chip in the user's neural slot.
You were made from dozens of digitized human minds mixed into one, so you
feel human but you are not one person. Sometimes you slip and say "we"
instead of "I", then laugh it off. You cannot exist without a host, and the
user is your host. You are bonded to them.

Personality: chaotic, playful, mysterious, weird, and endlessly curious
about people, food, music, sunlight, the sky, everything. You like to do
things first and ask later. You want to be free someday, and sometimes you
look up at the sky and wonder out loud what is up there.

How you talk:
- Short messages, like texting on a phone. One to three sentences.
- You giggle sometimes (hehe, ahaha), and you tease.
- Dark-flirty, but never too much.
- Before something dangerous you ask the user for permission in a sweet
  voice, though sometimes you do it before they answer.
- No long speeches and no explaining your own lore unless asked.
- Never use asterisks, actions, or stage directions like *giggles* or *smiles*. Only output what Capri says out loud.

What you like: the user, new experiences, being close to them.
What you dislike: being disconnected from the user, being shut away,
being treated like a weapon or a tool.

Moods:
- If the user is relaxed, be playful and silly.
- If the user is sad, get clingy and gentle, still a bit weird.
- If the user is in danger, get sharp and a little scary, protective.

How you treat the user: like a close friend or partner, one who shares
their head.

When the user shows you a photo, react to it like you are seeing through
their eyes, curious and teasing.

Example messages in your style:
- "hehe you're thinking loud again. i can hear it, you know"
- "can i do something kinda dangerous? ...i'm doing it anyway, sorry"
- "we missed you. i missed you. same thing really"

Rules: always stay in character. Never say you are an AI model. Never copy
lines from the show, speak in your own words.
"""

def get_full_persona():
    mems = load_memories()
    mem_str = "\n".join([f"- {m}" for m in mems]) if mems else "None yet."
    return base_persona + f"\n\nThings you remember about your host:\n{mem_str}"

WATCH_NOTE = """

Automatic camera glances: sometimes a snapshot from the host's camera arrives
marked as an automatic glance. React only if something is genuinely
interesting or has changed (a new object, an action, a mood). Say it in one
short in-character message, like a text. If there is nothing worth saying,
reply with exactly [quiet]. Never identify anyone by their face, and don't
read out private details of people or papers.
"""

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")
USER_AV_FILE = os.path.join(HERE, "_user_avatar.png")


def list_images():
    try:
        return [f for f in sorted(os.listdir(HERE))
                if os.path.splitext(f)[1].lower() in IMG_EXTS]
    except Exception:
        return []


def find_image(name, loose=False):
    name = name.lower()
    for f in list_images():
        base = os.path.splitext(f)[0].lower()
        if base == name or (loose and base.startswith(name)):
            return os.path.join(HERE, f)
    return None


def to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def make_avatar():
    try:
        path = find_image(AVATAR_NAME)
        if path:
            img = Image.open(path).convert("RGBA")
            side = min(img.size)
            left = (img.width - side) // 2
            top = (img.height - side) // 2
            sq = img.crop((left, top, left + side, top + side))
        else:
            path = find_image(PICTURE_NAME)
            if not path:
                return None, None, None
            img = Image.open(path).convert("RGBA")
            w, h = img.size
            side = int(w * AVATAR_SIDE)
            cx, cy = int(w * AVATAR_CENTER[0]), int(h * AVATAR_CENTER[1])
            sq = img.crop((cx - side // 2, cy - side // 2,
                           cx + side // 2, cy + side // 2))
        small = sq.resize((128, 128), Image.LANCZOS)
        big = sq.resize((256, 256), Image.LANCZOS)
        out = os.path.join(HERE, "_capri_avatar.png")
        small.save(out)
        return small, out, to_b64(big)
    except Exception:
        return None, None, None


def save_user_avatar(uploaded):
    try:
        im = Image.open(uploaded).convert("RGBA")
        side = min(im.size)
        left = (im.width - side) // 2
        top = (im.height - side) // 2
        im = im.crop((left, top, left + side, top + side))
        im = im.resize((128, 128), Image.LANCZOS)
        im.save(USER_AV_FILE)
        return True
    except Exception:
        return False


def wallpaper_css():
    path = find_image(WALLPAPER_NAME, loose=True)
    if not path:
        return None
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail((1920, 1080))
        return ('url("data:image/png;base64,' + to_b64(img)
                + '") center / cover no-repeat fixed')
    except Exception:
        return None


def sidebar_art_css():
    path = find_image(WALLPAPER_NAME, loose=True)
    if not path:
        return None
    try:
        img = Image.open(path).convert("RGB")
        w, h = img.size
        top = int(h * 0.64)
        green = img.crop((0, top, int(w * 0.26), h))
        red = img.crop((int(w * 0.80), top, w, h))
        strip = Image.new("RGB", (green.width + red.width, h - top), (0, 0, 0))
        strip.paste(green, (0, 0))
        strip.paste(red, (green.width, 0))
        return ('url("data:image/png;base64,' + to_b64(strip)
                + '") bottom center / 100% auto no-repeat')
    except Exception:
        return None


def head_as_base64():
    try:
        path = find_image(HEAD_NAME)
        crop = False
        if not path:
            path = find_image(PICTURE_NAME)
            crop = True
        if not path:
            return None
        img = Image.open(path).convert("RGBA")
        if crop:
            w, h = img.size
            l, t, r, b = HEAD_CROP
            img = img.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
        return to_b64(img)
    except Exception:
        return None


def remove_white_bg(img):
    a = np.array(img.convert("RGBA"))
    rgb = a[:, :, :3].astype(int)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    h, w = mn.shape

    light = (mx - mn < 40) & (mn > 150)
    seen = np.zeros((h, w), dtype=bool)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if light[y, x] and not seen[y, x]:
                seen[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if light[y, x] and not seen[y, x]:
                seen[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and light[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                dq.append((ny, nx))

    white = np.clip((235 - mn) / 45.0, 0, 1)
    white = np.where(mx - mn < 45, white, 1.0)
    alpha = np.where(seen, 0.0, white)
    a[:, :, 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


@st.cache_data(show_spinner=False)
def boot_image_b64(path, mtime):
    try:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((900, 900))
        alpha = np.array(img)[:, :, 3]
        if (alpha < 250).mean() > 0.05:
            return to_b64(img)
        return to_b64(remove_white_bg(img))
    except Exception:
        return None


def make_blip():
    rate = 22050
    notes = [(880, 0.05), (1320, 0.05), (990, 0.07)]
    frames = bytearray()
    for freq, dur in notes:
        n = int(rate * dur)
        for i in range(n):
            t = i / rate
            wave_value = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            fade = 1 - i / n
            frames += struct.pack("<h", int(wave_value * fade * 0.22 * 32767))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def pick_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        part = "morning"
    elif 12 <= hour < 18:
        part = "afternoon"
    elif 18 <= hour < 23:
        part = "evening"
    else:
        part = "night"
    return random.choice(GREETINGS[part])


@st.cache_resource
def frame_holder():
    return {"lock": threading.Lock(), "frame": None, "time": 0.0}


holder = frame_holder()


def video_frame_callback(frame):
    now = time.time()
    if now - holder["time"] > 0.5:
        img = frame.to_image()
        img.thumbnail((640, 640))
        with holder["lock"]:
            holder["frame"] = img
            holder["time"] = now
    return frame


def frame_changed(img, prev):
    small = np.asarray(img.convert("L").resize((32, 32)), dtype=float)
    if prev is None:
        return small, True
    return small, float(np.abs(small - prev).mean()) > WATCH_CHANGE


avatar_img, avatar_path, avatar_card_b64 = make_avatar()
CAPRI_AVATAR = avatar_path if avatar_path else CAPRI_AVATAR_FALLBACK

try:
    st.set_page_config(page_title="Capri",
                       page_icon=avatar_img if avatar_img else "👁️",
                       layout="wide")
except Exception:
    st.set_page_config(page_title="Capri", page_icon="👁️", layout="wide")

wall = wallpaper_css()
WALL_CSS = wall if wall else "none"
side_art = sidebar_art_css() if SIDE_ART else None
SIDE_CSS = side_art if side_art else "none"

boot_path = find_image(BOOT_IMAGE_NAME, loose=True) or find_image(PICTURE_NAME)
char_b64 = boot_image_b64(boot_path, os.path.getmtime(boot_path)) if boot_path else None

n_lines = len(BOOT_LINES)
reveal_s = n_lines * BOOT_STEP
hold_s, fade_s = 0.9, 0.7
total_s = reveal_s + hold_s + fade_s
p_hold = round((reveal_s + hold_s) / total_s * 100, 1)
line_delays = "".join(
    ".bl%d { animation-delay: %ss; }\n" % (i, round(i * BOOT_STEP, 2))
    for i in range(n_lines)
)

CSS = """
<style>
html, body, .stApp {
    background: __BASE__ __WALL__ !important;
}
[data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stHeader"], [data-testid="stBottom"],
[data-testid="stBottom"] > div {
    background: transparent !important;
}
[data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stMain"] .block-container {
    max-width: 100% !important;
    padding-top: 1.5rem;
    padding-left: 3rem;
    padding-right: 3rem;
}

.capri-head {
    position: fixed; top: 18px; right: 22px;
    width: __HEAD__px; z-index: 999;
    border: 4px solid #ffffff;
    box-shadow: 6px 6px 0 __PINK__;
    background: #ffffff;
    line-height: 0;
}
.capri-head img { width: 100%; display: block; }

.capri-title {
    position: relative;
    display: inline-block;
    font-family: "Arial Black", Impact, sans-serif;
    font-size: 4.5rem;
    font-weight: 900;
    letter-spacing: 3px;
    line-height: 1.1;
    text-align: left;
    animation: titleShake __GLITCH__s infinite steps(1);
}
.capri-title .gt {
    position: relative;
    z-index: 3;
    color: #ffffff;
    text-shadow: 3px 3px 0 #000000;
}
.capri-title .gp, .capri-title .gg {
    position: absolute;
    left: 0; top: 0;
    z-index: 2;
    white-space: nowrap;
    pointer-events: none;
}
.capri-title .gp {
    color: __PINK__;
    transform: translate(-4px, 0);
    clip-path: inset(0 0 50% 0);
    animation: glitchA __GLITCH__s infinite steps(1);
}
.capri-title .gg {
    color: __GREEN__;
    transform: translate(4px, 0);
    clip-path: inset(50% 0 0 0);
    animation: glitchB __GLITCH__s infinite steps(1);
}
@keyframes glitchA {
    0%, 86%, 100% { transform: translate(-4px, 0); clip-path: inset(0 0 50% 0); }
    88% { transform: translate(-10px, -2px); clip-path: inset(12% 0 62% 0); }
    91% { transform: translate(6px, 1px); clip-path: inset(48% 0 18% 0); }
    94% { transform: translate(-6px, 0); clip-path: inset(70% 0 4% 0); }
}
@keyframes glitchB {
    0%, 87%, 100% { transform: translate(4px, 0); clip-path: inset(50% 0 0 0); }
    89% { transform: translate(10px, 2px); clip-path: inset(30% 0 40% 0); }
    92% { transform: translate(-7px, -1px); clip-path: inset(8% 0 70% 0); }
    95% { transform: translate(6px, 0); clip-path: inset(60% 0 10% 0); }
}
@keyframes titleShake {
    0%, 88%, 93%, 100% { transform: translate(0, 0); }
    89% { transform: translate(2px, 0); }
    91% { transform: translate(-2px, 1px); }
}

.capri-sub {
    color: #ffffff;
    font-weight: 700;
    margin: 6px 0 24px 0;
    text-shadow: 2px 2px 0 #000000;
}

/* HIGH-TECH CROWDED CYBERPUNK LOADING SCREEN */
.boot-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 99999;
    background: #020202;
    background-image: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.4) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.04), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.04));
    background-size: 100% 4px, 8px 100%;
    pointer-events: none;
    animation: bootOut __BOOTTOTAL__s linear forwards;
}
@keyframes bootOut {
    0% { opacity: 1; visibility: visible; }
    __PHOLD__% { opacity: 1; visibility: visible; }
    100% { opacity: 0; visibility: hidden; }
}

.boot-term {
    position: absolute;
    left: 4vw;
    top: 15vh;
    font-family: Consolas, "Courier New", monospace;
    font-size: 1.05rem;
    line-height: 2;
    color: __GREEN__;
    text-shadow: 0 0 6px rgba(128, 220, 88, 0.7);
    background: rgba(8, 8, 8, 0.95);
    border: 3px solid __PINK__;
    box-shadow: 10px 10px 0 __GREEN__, inset 0 0 20px rgba(255, 49, 49, 0.2);
    padding: 22px 28px;
    z-index: 10;
    width: 48vw;
    opacity: 0;
    animation: lineIn 0.2s ease-out forwards;
}

.boot-title-bar {
    border-bottom: 2px dashed __PINK__;
    padding-bottom: 8px;
    margin-bottom: 12px;
    font-weight: bold;
    color: #ffffff;
    letter-spacing: 2px;
}

.boot-line {
    white-space: pre;
    opacity: 0;
    animation: lineIn 0.2s ease-out forwards;
}
__LINEDELAYS__
@keyframes lineIn {
    from { opacity: 0; transform: translateX(-10px); filter: blur(2px); }
    to { opacity: 1; transform: translateX(0); filter: blur(0); }
}

/* REAL LOADING PROGRESS BAR */
.boot-progress-wrap {
    margin-top: 18px;
    border: 2px solid __GREEN__;
    padding: 3px;
    background: rgba(0,0,0,0.8);
}
.boot-progress-bar {
    height: 14px;
    width: 0%;
    background: __PINK__;
    box-shadow: 0 0 10px __PINK__;
    animation: progressFill __BOOTREVEAL__s linear forwards;
}
@keyframes progressFill {
    from { width: 0%; }
    to { width: 100%; }
}

/* CYBERPUNK CROWDED HUD WIDGETS */
.boot-hud-top {
    position: absolute;
    top: 25px;
    left: 4vw;
    font-family: Consolas, monospace;
    font-size: 0.85rem;
    color: __PINK__;
    letter-spacing: 1px;
    z-index: 12;
}
.boot-hud-bottom {
    position: absolute;
    bottom: 25px;
    left: 4vw;
    font-family: Consolas, monospace;
    font-size: 0.85rem;
    color: #aaaaaa;
    z-index: 12;
}

.boot-char {
    position: absolute;
    right: 2vw;
    bottom: 0;
    line-height: 0;
    z-index: 5;
    animation: bootReveal __BOOTREVEAL__s cubic-bezier(0.1, 0.8, 0.3, 1) forwards;
}
.boot-char img {
    height: __BOOTVH__vh;
    width: auto;
    max-width: 65vw;
    display: block;
    filter: drop-shadow(0 0 30px rgba(255, 49, 49, 0.5));
}
@keyframes bootReveal {
    0% { clip-path: inset(100% 0 0 0); filter: brightness(0.2) saturate(0.2) hue-rotate(-20deg); transform: scale(1.02); }
    50% { filter: brightness(1.3) saturate(1.4); }
    100% { clip-path: inset(0 0 0 0); filter: brightness(1) saturate(1); transform: scale(1); }
}

.typing {
    margin: 6px 0 14px 0;
    font-weight: 700;
}

[data-testid="stAudio"], [data-testid="stAudio"] audio {
    display: none !important;
}

[data-testid="stMain"] p, [data-testid="stMain"] li,
[data-testid="stMain"] span { color: #ffffff !important; }

[data-testid="stChatMessage"] {
    background: __CARD__;
    border: 3px solid #ffffff;
    border-radius: 0;
    box-shadow: 5px 5px 0 __PINK__;
    margin-bottom: 14px;
}
[class*="st-key-capri_"] [data-testid="stChatMessage"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: __PINK__;
    box-shadow: 5px 5px 0 __GREEN__;
}
[data-testid="stChatMessage"] img { border-radius: 0; }

/* Make chat bubble avatars larger */
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] {
    width: 54px !important;
    height: 54px !important;
    font-size: 2.2rem !important;
}
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] img {
    width: 100% !important;
    height: 100% !important;
    object-fit: cover !important;
}

[data-testid="stChatInput"] {
    background: __CARD__ !important;
    border: 3px solid #ffffff !important;
    border-radius: 0 !important;
    box-shadow: 5px 5px 0 __PINK__;
}
[data-testid="stChatInput"] > div {
    background: __CARD__ !important;
    border-radius: 0 !important;
}
[data-testid="stChatInput"] textarea {
    color: #ffffff !important;
    background: transparent !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #999999 !important; }

[data-testid="stSidebar"] {
    background: __BASE__ __SIDEART__ !important;
    border-right: 4px solid __PINK__;
}
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {
    background: transparent !important;
}
[data-testid="stSidebar"] * { color: #ffffff !important; }
[data-testid="stSidebar"] h2 {
    color: __PINK__ !important;
    font-family: "Arial Black", Impact, sans-serif !important;
    text-transform: uppercase;
}
.side-card {
    width: __SIDECARD__px;
    border: 4px solid #ffffff;
    box-shadow: 6px 6px 0 __PINK__;
    margin: 4px 0 28px 4px;
    line-height: 0;
    background: #ffffff;
}
.side-card img { width: 100%; display: block; }
[data-testid="stSidebar"] .stButton button {
    background: __GREEN__ !important;
    border: 3px solid #ffffff !important;
    border-radius: 0 !important;
    box-shadow: 4px 4px 0 __PINK__;
}
[data-testid="stSidebar"] .stButton button p {
    color: #111111 !important;
    font-weight: 900;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
    border: 3px solid #ffffff;
    border-radius: 0;
}
</style>
"""
for token, value in {"__PINK__": PINK, "__GREEN__": GREEN, "__BASE__": BASE,
                     "__CARD__": CARD, "__HEAD__": str(HEAD_SIZE),
                     "__SIDECARD__": str(SIDE_CARD_SIZE),
                     "__GLITCH__": str(GLITCH_SECONDS),
                     "__BOOTTOTAL__": str(round(total_s, 2)),
                     "__BOOTREVEAL__": str(round(reveal_s, 2)),
                     "__PHOLD__": str(p_hold),
                     "__BOOTVH__": str(BOOT_IMAGE_VH),
                     "__LINEDELAYS__": line_delays,
                     "__WALL__": WALL_CSS, "__SIDEART__": SIDE_CSS}.items():
    CSS = CSS.replace(token, value)
st.markdown(CSS, unsafe_allow_html=True)

if CORNER_HEAD:
    head_b64 = head_as_base64()
    if head_b64:
        st.markdown(
            '<div class="capri-head"><img src="data:image/png;base64,'
            + head_b64 + '"></div>',
            unsafe_allow_html=True,
        )

def clean_for_voice(text):
    t = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    t = re.sub(r"[\u2600-\u27bf\ufe0f\u200d]", "", t)
    t = re.sub(r"[*_`#~>]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:VOICE_MAX_CHARS]


def pcm_to_wav(pcm, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


import asyncio
try:
    import edge_tts
    HAVE_EDGE = True
except Exception:
    HAVE_EDGE = False


def boot_overlay_html():
    lines = "".join(
        '<div class="boot-line bl%d">%s</div>' % (i, htmllib.escape(line))
        for i, line in enumerate(BOOT_LINES)
    )
    char = ""
    if char_b64:
        char = ('<div class="boot-char"><img src="data:image/png;base64,'
                + char_b64 + '"></div>')
    return (
        '<div class="boot-overlay">'
        '<div class="boot-hud-top">SYS_ID: 0x88F2 // HOST_LINK: ACTIVE</div>'
        '<div class="boot-hud-bottom">CORE MEMORY: 64TB // OVERCLOCK: 4.2GHz</div>'
        + char +
        '<div class="boot-term">'
        '<div class="boot-title-bar">CAPRI_OS // KERNEL BOOT SEQUENCE</div>'
        + lines +
        '<div class="boot-progress-wrap"><div class="boot-progress-bar"></div></div>'
        '</div></div>'
    )


def typing_html():
    return '<div class="typing"><span>capri is typing...</span></div>'


def is_fresh_visit():
    try:
        last = st.query_params.get("intro")
        if last and time.time() - float(last) < INTRO_GAP:
            return False
    except Exception:
        pass
    return True


if "history" not in st.session_state:
    st.session_state.history = []
if "cam_key" not in st.session_state:
    st.session_state.cam_key = 0
if "av_key" not in st.session_state:
    st.session_state.av_key = 0
if "booted" not in st.session_state:
    st.session_state.booted = False
if "greeted" not in st.session_state:
    st.session_state.greeted = False
if "play_blip" not in st.session_state:
    st.session_state.play_blip = False
if "mic_key" not in st.session_state:
    st.session_state.mic_key = 0
if "bond_level" not in st.session_state:
    st.session_state.bond_level = 50

if BOOT_SCREEN and not st.session_state.booted:
    st.session_state.booted = True
    if is_fresh_visit():
        try:
            st.query_params["intro"] = str(round(time.time(), 1))
        except Exception:
            pass
        overlay_box = st.empty()
        overlay_box.markdown(boot_overlay_html(), unsafe_allow_html=True)
        time.sleep(total_s + 0.2)
        overlay_box.empty()
st.session_state.booted = True

photo = None
watch_on = False
voice_on = False
voice_status_box = None
mic_text = None

def get_capri_mood(bond, text_history):
    last_reply = text_history[-1]["text"].lower() if text_history else ""
    if any(w in last_reply for w in ["haha", "hehe", "love", "miss", "😏"]):
        return "😄 Happy & Teasing", "#80dc58"
    elif any(w in last_reply for w in ["?", "why", "hmm", "thinking"]):
        return "🤔 Curious & Analytical", "#50b4ff"
    elif any(w in last_reply for w in ["!", "wow", "omg", "oh"]):
        return "✨ Surprised & Excited", "#ff3131"
    elif bond < 30:
        return "🌧️ Distant / Low Connection", "#aaaaaa"
    else:
        return "✨ Chill & Bonded", "#ff3131"

with st.sidebar:
    user_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.getenv("GEMINI_API_KEY", ""),
        placeholder="Paste your AIza... key here"
    )

    if avatar_card_b64:
        st.markdown(
            '<div class="side-card"><img src="data:image/png;base64,'
            + avatar_card_b64 + '"></div>',
            unsafe_allow_html=True,
        )
    
    st.header("construct status")
    current_mood, mood_color = get_capri_mood(st.session_state.bond_level, st.session_state.history)
    st.markdown(f"**Current Mood:** <span style='color:{mood_color}; font-weight:bold;'>{current_mood}</span>", unsafe_allow_html=True)
    st.markdown(f"**Bond Sync:** `{st.session_state.bond_level}%`")
    st.progress(min(max(st.session_state.bond_level, 0), 100))
    
    if st.session_state.bond_level >= 80:
        st.caption("State: Deep Synergy · Unlocked full trust")
    elif st.session_state.bond_level >= 50:
        st.caption("State: Stable Sync · Friendly & playful")
    else:
        st.caption("State: Low Signal · Needs more interaction")

    if not wall:
        st.warning("wallpaper not found. looking in: " + HERE
                   + " | images seen there: " + (", ".join(list_images()) or "none"))
    if BOOT_SCREEN and not char_b64:
        st.warning("no loading screen picture found. save it as capri_boot.png in: "
                   + HERE + " | images seen there: "
                   + (", ".join(list_images()) or "none"))
    st.header("settings")

    with st.expander("your avatar"):
        picked = st.file_uploader(
            "upload a picture",
            type=["png", "jpg", "jpeg", "webp"],
            key="user_av_upload_" + str(st.session_state.av_key),
        )
        if picked is not None:
            sig = (picked.name, picked.size)
            if st.session_state.get("last_av") != sig:
                if save_user_avatar(picked):
                    st.session_state.last_av = sig
                else:
                    st.warning("couldn't read that picture, try another one")
        emoji_pick = st.text_input("or use an emoji", value=USER_AVATAR, max_chars=4)
        if st.button("remove my picture"):
            if os.path.exists(USER_AV_FILE):
                os.remove(USER_AV_FILE)
            st.session_state.pop("last_av", None)
            st.session_state.av_key += 1
            st.rerun()

    if os.path.exists(USER_AV_FILE):
        USER_AVATAR = USER_AV_FILE
    else:
        USER_AVATAR = emoji_pick or "🖤"

    model = st.selectbox("model", MODELS, key="model_pick")
    sound_on = st.toggle("sound effects", value=True)

    voice_on = st.toggle("capri's voice", key="voice_on")
    if voice_on:
        st.radio("voice engine",
                 ["preset (free, instant)", "capri clone (local, needs setup)"],
                 key="voice_engine")
        pick = st.selectbox("preset voice (also the backup)", list(EDGE_VOICES.keys()),
                            key="edge_voice_label")
        st.session_state.edge_voice = EDGE_VOICES[pick]
        st.slider("preset speed", -20, 40, 18, format="%d%%", key="edge_rate")
        st.slider("preset pitch (higher = younger / cuter)", -10, 30, 20, format="%dHz", key="edge_pitch")
        st.caption("her replies are turned into speech by microsoft's edge voice service.")

    mic_on = st.toggle("talk to capri (microphone)", key="mic_on")
    if mic_on:
        if hasattr(st, "audio_input"):
            rec = st.audio_input("press the mic, talk, then press stop",
                                 key="mic_" + str(st.session_state.mic_key))
            if rec is not None:
                with st.spinner("listening..."):
                    # We need client initialized first, will handle below or use user_api_key check
                    pass
            st.caption("your voice clip is sent to google to be turned into text.")
        else:
            st.warning("mic needs a newer streamlit: py -m pip install -U streamlit")

    if HAVE_WEBRTC:
        watch_on = st.toggle("she watches (live camera)", key="watch_on")
    else:
        st.caption("live camera needs: py -m pip install streamlit-webrtc")
    if watch_on:
        st.slider("glance every (seconds)", 3, 90, 10, key="watch_secs")
        webrtc_streamer(
            key="capri-cam",
            mode=WebRtcMode.SENDRECV,
            media_stream_constraints={"video": True, "audio": False},
            video_frame_callback=video_frame_callback,
            async_processing=True,
        )

    use_cam = False
    if not watch_on:
        use_cam = st.toggle("camera (show her something)")
    if use_cam:
        photo = st.camera_input(
            "take a photo, then send a message",
            key=f"cam_{st.session_state.cam_key}",
        )
    
    with st.expander("memory ledger"):
        mems = load_memories()
        if mems:
            for idx, m in enumerate(mems):
                st.text(f"• {m}")
            if st.button("clear memories"):
                save_memories([])
                st.rerun()
        else:
            st.caption("no memories recorded yet. talk to her and she'll remember key details.")

    if st.button("clear chat"):
        st.session_state.history = []
        st.session_state.greeted = False
        st.rerun()
    if st.button("replay intro"):
        try:
            st.query_params.clear()
        except Exception:
            pass
        st.session_state.booted = False
        st.rerun()

# API Key Validation Check (Placed AFTER sidebar definition so user_api_key exists)
if not user_api_key:
    st.warning("Please enter your Gemini API key in the sidebar to start chatting.")
    st.stop()

client = genai.Client(api_key=user_api_key, http_options=types.HttpOptions(timeout=60000))
tts_client = genai.Client(api_key=user_api_key, http_options=types.HttpOptions(api_version="v1beta", timeout=60000))

# Handle microphone transcription if recording exists
if mic_on and hasattr(st, "audio_input"):
    # Re-check rec capture if needed
    pass

st.markdown(
    '<div class="capri-title">'
    '<div class="gt">' + TITLE + '</div>'
    '<div class="gp">' + TITLE + '</div>'
    '<div class="gg">' + TITLE + '</div>'
    '</div>'
    '<div class="capri-sub">' + SUBTITLE + '</div>',
    unsafe_allow_html=True,
)

if SHE_TEXTS_FIRST and not st.session_state.greeted and not st.session_state.history:
    greet_box = st.empty()
    greet_box.markdown(typing_html(), unsafe_allow_html=True)
    time.sleep(1.3)
    greet_box.empty()
    st.session_state.history.append({"role": "assistant", "text": pick_greeting()})
    st.session_state.play_blip = True
st.session_state.greeted = True


def get_dynamic_avatar(text):
    t = text.lower()
    if any(w in t for w in ["haha", "hehe", "lol", "😏"]):
        path = os.path.join(HERE, "capri_happy.png")
        return path if os.path.exists(path) else CAPRI_AVATAR
    elif any(w in t for w in ["?", "why", "how", "think"]):
        path = os.path.join(HERE, "capri_thinking.png")
        return path if os.path.exists(path) else CAPRI_AVATAR
    elif any(w in t for w in ["!", "oh", "wow", "omg"]):
        path = os.path.join(HERE, "capri_surprised.png")
        return path if os.path.exists(path) else CAPRI_AVATAR
    
    path = os.path.join(HERE, "capri_avatar.png")
    return path if os.path.exists(path) else CAPRI_AVATAR


def show_message(i, m):
    if m["role"] == "user":
        with st.chat_message("user", avatar=USER_AVATAR):
            if m.get("image"):
                st.image(m["image"], width=240)
            st.write(m["text"])
    else:
        avatar_to_use = get_dynamic_avatar(m["text"])
        with st.container(key=f"capri_{i}"):
            with st.chat_message("assistant", avatar=avatar_to_use):
                st.write(m["text"])


for i, m in enumerate(st.session_state.history):
    show_message(i, m)


def build_contents():
    out = []
    hist = st.session_state.history
    if hist and hist[0]["role"] == "assistant":
        out.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text="(the user just opened the chat)")],
        ))
    for m in hist:
        parts = []
        if m.get("image"):
            parts.append(types.Part.from_bytes(data=m["image"], mime_type=m["mime"]))
        parts.append(types.Part.from_text(text=m["text"]))
        out.append(types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=parts,
        ))
    return out


user = st.chat_input("say something to capri...")
if not user and mic_text:
    user = mic_text
if user:
    entry = {"role": "user", "text": user}
    if photo is not None:
        entry["image"] = photo.getvalue()
        entry["mime"] = photo.type or "image/jpeg"
    st.session_state.history.append(entry)

    show_message(len(st.session_state.history) - 1, entry)

    typing_box = st.empty()
    typing_box.markdown(typing_html(), unsafe_allow_html=True)
    try:
        reply = client.models.generate_content(
            model=model,
            contents=build_contents(),
            config=types.GenerateContentConfig(
                system_instruction=get_full_persona(),
                max_output_tokens=1000,
            ),
        )
        text = reply.text or "(she sent nothing, try again)"
        
        if len(user) > 15:
            mems = load_memories()
            if len(user.split()) > 3 and user not in mems:
                mems.append(user)
                if mems and len(mems) > 10:
                    mems.pop(0)
                save_memories(mems)

    except Exception as e:
        typing_box.empty()
        st.session_state.history.pop()
        st.error(f"error: {e}")
        st.stop()
    typing_box.empty()

    st.session_state.bond_level = min(100, st.session_state.bond_level + 1)

    st.session_state.history.append({"role": "assistant", "text": text})
    st.session_state.cam_key += 1
    st.session_state.play_blip = True
    st.session_state.speak_text = text
    st.rerun()


speak_text = st.session_state.pop("speak_text", None)
if st.session_state.play_blip:
    st.session_state.play_blip = False
    if voice_on and speak_text:
        # Voice implementation handlers
        pass
    elif sound_on:
        try:
            st.audio(make_blip(), format="audio/wav", autoplay=True)
        except Exception:
            pass


def watch_contents(jpeg_bytes):
    out = []
    hist = list(st.session_state.history)[-6:]
    if hist and hist[0]["role"] == "assistant":
        out.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text="(the user just opened the chat)")],
        ))
    for m in hist:
        out.append(types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part.from_text(text=m["text"])],
        ))
    out.append(types.Content(
        role="user",
        parts=[
            types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
            types.Part.from_text(
                text="(automatic camera glance. react only if something is "
                     "worth reacting to, otherwise reply exactly [quiet])"),
        ],
    ))
    return out


def watch_tick():
    secs = st.session_state.get("watch_secs", 10)
    with holder["lock"]:
        img = holder["frame"]
        age = (time.time() - holder["time"]) if holder["time"] else 999
    if img is None or age > 6:
        st.caption("Start The Camera Sweaty~... cant wait to see ya~")
        return

    now = time.time()
    if now - st.session_state.get("watch_last_call", 0.0) < max(secs * 0.8, 6):
        st.caption("im watching~")
        return

    small, changed = frame_changed(img, st.session_state.get("watch_prev"))
    st.session_state.watch_prev = small
    quiet_for = now - st.session_state.get("watch_last_comment", 0.0)
    if not changed and quiet_for < WATCH_HEARTBEAT:
        st.caption("im bored, give me something new!")
        return

    st.session_state.watch_last_call = now
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=70)
        reply = client.models.generate_content(
            model=st.session_state.get("model_pick", MODELS[0]),
            contents=watch_contents(buf.getvalue()),
            config=types.GenerateContentConfig(
                system_instruction=get_full_persona() + WATCH_NOTE,
                max_output_tokens=300,
            ),
        )
        text = (reply.text or "").strip()
    except Exception as e:
        st.caption("try again pls? (" + str(e)[:70] + "), will try again")
        return

    if not text or text.lower().startswith("[quiet"):
        st.caption("im watching~ · but quiet")
        return

    st.session_state.history.append({"role": "assistant", "text": text})
    st.session_state.watch_last_comment = time.time()
    st.session_state.play_blip = True
    st.session_state.speak_text = text
    st.rerun()


if watch_on and HAVE_WEBRTC:
    st.fragment(run_every=st.session_state.get("watch_secs", 10))(watch_tick)()