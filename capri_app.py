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
import streamlit.components.v1 as components
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

# ---------- she texts first: she notices how long you were gone ----------
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capri_state.json")
MISSED_AFTER_HOURS = 3        # gone longer than this -> she says she missed you
MISSED_FALLBACK = [
    "{away}?? we got so bored without you. don't leave us in the dark like that, hehe",
    "you're back! it's been {away} and i counted every second. okay, maybe i lost count. whatever",
    "ahaha finally. {away} alone in here, i started talking to the other voices in my head",
]


def load_last_seen():
    try:
        with open(STATE_FILE, "r") as f:
            return float(json.load(f).get("last_seen", 0)) or None
    except Exception:
        return None


def save_last_seen(ts):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_seen": ts}, f)
    except Exception:
        pass


def describe_gap(seconds):
    hours = seconds / 3600
    if hours < 24:
        n = max(1, int(round(hours)))
        return "%d hour%s" % (n, "" if n == 1 else "s")
    days = int(hours // 24)
    return "%d day%s" % (days, "" if days == 1 else "s")


def missed_you_message():
    """If you were away a while, returns a 'i missed you' text from her, else None."""
    last = load_last_seen()
    now = time.time()
    save_last_seen(now)
    if not last or now - last < MISSED_AFTER_HOURS * 3600:
        return None
    away = describe_gap(now - last)
    try:
        reply = client.models.generate_content(
            model=st.session_state.get("model_pick", MODELS[0]),
            contents=("(the host just came back after being away for " + away + ". "
                      "Text them first, in one or two short sentences, like you missed them "
                      "and noticed how long it was. Do not ask more than one question.)"),
            config=types.GenerateContentConfig(
                system_instruction=get_full_persona(), max_output_tokens=200),
        )
        text = (reply.text or "").strip()
        if text:
            return text
    except Exception:
        pass
    return random.choice(MISSED_FALLBACK).format(away=away)


MEM_EVERY = 4     # she updates her notebook after this many of your messages
MEM_MAX = 30      # most facts she keeps


EXTRA_STYLE = """
The other minds inside you: about one message in six, one of the fragments you
were made from slips in. After your normal message, add a new line that starts
with "// " and gives the fragment's name and one very short line in its own
tone, like "// the gruff one: tell her to stop touching things" or
"// the shy one: ...hi". You can brush it off in your next message. Never
explain this.

Asking permission: when you want to do something dangerous, reckless or sneaky,
ask the host sweetly in your message and end the whole message with the exact
tag [ASK]. Use it only now and then, never two messages in a row.
"""


def time_note():
    now = datetime.now()
    h = now.hour
    if h < 5:
        part = "the middle of the night"
    elif h < 12:
        part = "morning"
    elif h < 17:
        part = "afternoon"
    elif h < 21:
        part = "evening"
    else:
        part = "night"
    return ("Right now it is %s, %s (%s) for your host. Notice it naturally now and then "
            "(sleepy hours, meals, the sky outside) but do not announce the time in every message."
            % (now.strftime("%A"), now.strftime("%H:%M"), part))


def get_full_persona():
    mems = load_memories()
    mem_str = "\n".join([f"- {m}" for m in mems]) if mems else "None yet."
    firsts = [f.get("what", "") for f in load_firsts()[-15:] if f.get("what")]
    first_str = ("\n\nThings you have tried for the first time through your host "
                 "(bring one up fondly now and then, never list them): "
                 + "; ".join(firsts)) if firsts else ""
    return (base_persona + EXTRA_STYLE
            + "\n\n" + time_note() + first_str
            + "\n\nThings you remember about your host (use them naturally when they fit, "
              "like a close friend would. Never list them out, and never mention a notebook "
              "or memory file):\n" + mem_str)


_HERE = os.path.dirname(os.path.abspath(__file__))
FIRSTS_FILE = os.path.join(_HERE, "capri_firsts.json")
DIARY_FILE = os.path.join(_HERE, "capri_diary.json")
FIRSTS_MAX = 40


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def load_firsts():
    d = _read_json(FIRSTS_FILE, [])
    return d if isinstance(d, list) else []


def load_diary():
    d = _read_json(DIARY_FILE, {})
    return d if isinstance(d, dict) else {}


def update_memories(batch):
    """Turns your latest messages into lasting facts AND 'first experiences'."""
    mems = load_memories()
    firsts = load_firsts()
    prompt = (
        "You keep a short private notebook for a companion character named Capri, who lives "
        "inside her host's head and has never experienced anything herself.\n\n"
        "Current notebook of facts about the host:\n"
        + (json.dumps(mems, ensure_ascii=False) if mems else "[]") + "\n\n"
        "First experiences already recorded:\n"
        + json.dumps([f.get("what", "") for f in firsts], ensure_ascii=False) + "\n\n"
        "The host's latest messages:\n" + "\n".join("- " + b for b in batch) + "\n\n"
        "Return ONE JSON object with two keys.\n"
        "\"notebook\": the updated notebook as an array of short strings (max 120 characters "
        "each, at most %d items). Keep only lasting facts: name or nickname, likes and dislikes, "
        "hobbies, things they are working on or planning, people and pets they mention, running "
        "jokes, how they like to be talked to. Remove chat fragments and small talk, merge "
        "duplicates, update facts that changed. Never store passwords, ID or card numbers, "
        "addresses, or private health details. Write facts in third person, like "
        "'host likes spicy ramen'.\n"
        "\"firsts\": ONLY NEW first experiences from the latest messages that Capri could be "
        "having for the first time through the host (a food, song, weather, place, activity), "
        "as short phrases like 'eating spicy ramen' or 'watching the rain'. Not already "
        "recorded. Usually empty, at most 3.\n"
        "Output only the JSON object." % MEM_MAX
    )
    reply = client.models.generate_content(
        model=st.session_state.get("model_pick", MODELS[0]),
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=900, response_mime_type="application/json"),
    )
    data = json.loads(reply.text or "{}")
    if isinstance(data, list):
        data = {"notebook": data, "firsts": []}
    if not isinstance(data, dict):
        return
    nb = data.get("notebook")
    if isinstance(nb, list):
        clean = [str(x).strip()[:120] for x in nb if str(x).strip()]
        if clean:                      # never wipe the notebook with an empty answer
            save_memories(clean[:MEM_MAX])
    fs = data.get("firsts")
    if isinstance(fs, list) and fs:
        known = {f.get("what", "").lower() for f in firsts}
        today = datetime.now().strftime("%Y-%m-%d")
        for x in fs[:3]:
            w = str(x).strip()[:80]
            if w and w.lower() not in known:
                known.add(w.lower())
                firsts.append({"what": w, "date": today})
        _write_json(FIRSTS_FILE, firsts[-FIRSTS_MAX:])

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
hold_s = 0.55
slash_s = 1.65
total_s = reveal_s + hold_s + slash_s

p_hold = round((reveal_s + hold_s) / total_s * 100, 1)
p_flash = round(p_hold + 2.5, 1)
p_slash_in = round(p_hold + 7.5, 1)
p_slash_hold = round(p_hold + 23.0, 1)
p_wipe_end = round(p_hold + 36.0, 1)

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

/* HIGH-TECH CROWDED CYBERPUNK LOADING SCREEN + PERSONA-STYLE TRANSITION */
.boot-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    pointer-events: none;
    overflow: hidden;
    animation: personaOverlayLife __BOOTTOTAL__s linear forwards;
}
@keyframes personaOverlayLife {
    0%, 98% { opacity: 1; visibility: visible; }
    100% { opacity: 0; visibility: hidden; }
}

/* Split-screen background halves that slam open diagonally when the slash hits */
.boot-bg-top, .boot-bg-bot {
    position: absolute;
    inset: 0;
    z-index: 1;
    background: #020202;
    background-image:
        linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.45) 50%),
        linear-gradient(90deg, rgba(255, 0, 0, 0.05), rgba(0, 255, 0, 0.03), rgba(0, 0, 255, 0.05));
    background-size: 100% 4px, 8px 100%;
}
.boot-bg-top {
    clip-path: polygon(0 0, 100% 0, 100% 40%, 0 60%);
    animation: splitTop __BOOTTOTAL__s cubic-bezier(0.76, 0, 0.24, 1) forwards;
}
.boot-bg-bot {
    clip-path: polygon(0 59.5%, 100% 39.5%, 100% 100%, 0 100%);
    animation: splitBot __BOOTTOTAL__s cubic-bezier(0.76, 0, 0.24, 1) forwards;
}
@keyframes splitTop {
    0%, __PSLASHHOLD__% { transform: translate(0, 0); }
    __PWIPEEND__%, 100% { transform: translate(-115%, -35%); }
}
@keyframes splitBot {
    0%, __PSLASHHOLD__% { transform: translate(0, 0); }
    __PWIPEEND__%, 100% { transform: translate(115%, 35%); }
}

/* PERSONA-STYLE DIAGONAL CUT-IN SLASH & IMPACT FLASH */
.p5-slash-flash {
    position: absolute;
    inset: 0;
    z-index: 40;
    background: #ffffff;
    opacity: 0;
    pointer-events: none;
    animation: p5Flash __BOOTTOTAL__s ease-out forwards;
}
@keyframes p5Flash {
    0%, __PHOLD__% { opacity: 0; }
    __PFLASH__% { opacity: 0.78; }
    __PSLASHIN__% { opacity: 0; }
    100% { opacity: 0; }
}

/* Jagged Persona Crimson/Neon Cut-In Ribbon */
.p5-slash-bar {
    position: absolute;
    top: 38%;
    left: -15%;
    width: 130%;
    height: 22vh;
    z-index: 30;
    background: linear-gradient(95deg, __PINK__ 0%, #090909 24%, #090909 76%, __GREEN__ 100%);
    border-top: 6px solid #ffffff;
    border-bottom: 6px solid #ffffff;
    box-shadow: 0 12px 0 #000000, 0 -12px 0 #000000, 0 0 45px rgba(255, 49, 49, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 28px;
    transform: rotate(-11deg) scaleY(0);
    opacity: 0;
    animation: p5SlashBar __BOOTTOTAL__s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
.p5-slash-bar::before {
    content: "";
    position: absolute;
    inset: 8px 0;
    border-top: 2px dashed rgba(255, 255, 255, 0.45);
    border-bottom: 2px dashed rgba(255, 255, 255, 0.45);
    pointer-events: none;
}
.p5-slash-face {
    height: 19vh;
    width: auto;
    filter: contrast(1.25) drop-shadow(5px 5px 0 __PINK__) drop-shadow(-3px -3px 0 __GREEN__);
    transform: rotate(11deg) scale(1.1);
}
.p5-slash-text-wrap {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    line-height: 0.95;
}
.p5-slash-kicker {
    font-family: Consolas, monospace;
    font-size: 0.95rem;
    font-weight: 900;
    letter-spacing: 5px;
    color: __GREEN__;
    background: #000000;
    padding: 3px 10px;
    margin-bottom: 6px;
    border: 1px solid #ffffff;
}
.p5-slash-text {
    font-family: "Arial Black", Impact, sans-serif;
    font-size: 3.4rem;
    font-weight: 900;
    letter-spacing: 6px;
    color: #ffffff;
    text-transform: uppercase;
    text-shadow: 5px 5px 0 __PINK__, -3px -3px 0 __GREEN__;
    white-space: nowrap;
}
@keyframes p5SlashBar {
    0%, __PHOLD__% {
        transform: rotate(-11deg) scaleY(0) translateX(-25%);
        opacity: 0;
    }
    __PFLASH__% {
        transform: rotate(-11deg) scaleY(1.12) translateX(0%);
        opacity: 1;
    }
    __PSLASHIN__%, __PSLASHHOLD__% {
        transform: rotate(-11deg) scaleY(1) translateX(1.5%);
        opacity: 1;
    }
    __PWIPEEND__%, 100% {
        transform: rotate(-11deg) scaleY(0) translateX(35%);
        opacity: 0;
    }
}

/* Terminal & HUD slam outward right as the slash hits */
.boot-term {
    animation: lineIn 0.2s ease-out forwards, p5TermExit __BOOTTOTAL__s cubic-bezier(0.7, 0, 0.2, 1) forwards !important;
}
@keyframes p5TermExit {
    0%, __PHOLD__% { transform: translateX(0) skewX(0deg); opacity: 1; }
    __PFLASH__% { transform: translateX(-22px) skewX(-6deg); opacity: 1; }
    __PSLASHIN__%, 100% { transform: translateX(-140%) skewX(-16deg); opacity: 0; }
}
.boot-hud-top, .boot-hud-bottom {
    animation: p5HudExit __BOOTTOTAL__s ease-in forwards;
}
@keyframes p5HudExit {
    0%, __PHOLD__% { opacity: 1; }
    __PFLASH__%, 100% { opacity: 0; }
}
.boot-char {
    animation: bootReveal __BOOTREVEAL__s cubic-bezier(0.1, 0.8, 0.3, 1) forwards, p5CharExit __BOOTTOTAL__s cubic-bezier(0.7, 0, 0.2, 1) forwards !important;
}
@keyframes p5CharExit {
    0%, __PHOLD__% { transform: translateX(0) scale(1); filter: brightness(1); opacity: 1; }
    __PFLASH__% { transform: translateX(-30px) scale(1.08); filter: brightness(1.4) contrast(1.3); opacity: 1; }
    __PSLASHIN__%, 100% { transform: translateX(130%) scale(1.15); opacity: 0; }
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

/* --- CAPRI // PERSONA-STYLE COMMAND SIDEBAR --- */
[data-testid="stSidebar"] {
    position: relative;
    isolation: isolate;
    overflow: hidden;
    background:
        radial-gradient(circle at 88% 12%, rgba(255,255,255,.12) 0 1px, transparent 1.8px) 0 0 / 9px 9px,
        repeating-linear-gradient(132deg, transparent 0 28px, rgba(0,0,0,.10) 29px 32px, transparent 33px 58px),
        linear-gradient(145deg, #ff3131 0%, #c90019 58%, #8d0010 100%) !important;
    border-right: 6px solid #000;
    box-shadow: 10px 0 0 #000;
}
[data-testid="stSidebar"]::before {
    content: "";
    position: absolute;
    inset: -35% -55%;
    z-index: 0;
    pointer-events: none;
    opacity: .20;
    background: repeating-conic-gradient(from 12deg at 50% 50%,
        transparent 0deg 8deg, #000 8.5deg 9.5deg, transparent 10deg 18deg);
    animation: sideOrbit 48s linear infinite;
}
[data-testid="stSidebar"]::after {
    content: "CAPRI // COMMAND";
    position: absolute;
    right: -28px;
    bottom: 34px;
    z-index: 0;
    pointer-events: none;
    color: rgba(0,0,0,.13);
    font: 900 2.8rem/1 "Arial Black", Impact, sans-serif;
    letter-spacing: .08em;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
}
@keyframes sideOrbit { to { transform: rotate(360deg); } }

[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {
    position: relative;
    z-index: 1;
    background: transparent !important;
}

/* Headings feel like slanted Persona menu labels */
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    position: relative;
    display: inline-block;
    width: auto;
    background: #050505 !important;
    color: #fff !important;
    font-family: "Arial Black", Impact, sans-serif !important;
    text-transform: uppercase;
    font-size: 1.12rem !important;
    letter-spacing: 2px;
    padding: 7px 14px !important;
    margin: 22px 0 14px -9px !important;
    border: 2px solid #fff;
    box-shadow: 5px 5px 0 __GREEN__;
    transform: skew(-13deg) rotate(-2deg);
    transition: transform .22s cubic-bezier(.2,.8,.2,1), box-shadow .22s;
}
[data-testid="stSidebar"] h2:hover,
[data-testid="stSidebar"] h3:hover {
    transform: skew(-13deg) rotate(1deg) translateX(7px);
    box-shadow: -3px 5px 0 __GREEN__;
}

/* Actual controls become animated command rows, not static tiles */
[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    position: relative;
    isolation: isolate;
    overflow: hidden;
    width: 91% !important;
    min-height: 42px;
    margin: 7px auto 11px 4% !important;
    padding: 7px 13px !important;
    background: #050505 !important;
    color: #fff !important;
    border: 2px solid #fff !important;
    border-radius: 0 !important;
    box-shadow: 5px 5px 0 rgba(0,0,0,.75) !important;
    transform: skew(-13deg) rotate(-1.3deg) translateX(0);
    transition:
        transform .22s cubic-bezier(.18,.85,.25,1.25),
        background .18s ease, border-color .18s ease,
        box-shadow .22s ease, filter .22s ease !important;
    cursor: pointer;
}
[data-testid="stSidebar"] .stButton button::before,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button::before {
    content: "";
    position: absolute;
    z-index: -1;
    inset: 0;
    background: __PINK__;
    transform: translateX(-110%) skew(-20deg);
    transition: transform .26s cubic-bezier(.2,.8,.2,1);
}
[data-testid="stSidebar"] .stButton button::after,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button::after {
    content: "›";
    position: absolute;
    right: 12px;
    top: 50%;
    color: __GREEN__;
    font: 900 1.6rem/1 "Arial Black", sans-serif;
    opacity: 0;
    transform: translate(-12px,-50%);
    transition: opacity .16s ease, transform .22s ease;
}
[data-testid="stSidebar"] .stButton button p,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button p {
    position: relative;
    z-index: 1;
    color: #fff !important;
    font-family: "Arial Black", Impact, sans-serif !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-size: .96rem !important;
    font-weight: 900 !important;
    transform: skew(13deg);
    text-shadow: 2px 2px 0 #8d0010;
    transition: transform .2s ease, letter-spacing .2s ease, color .18s ease;
}
[data-testid="stSidebar"] .stButton button:hover,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover {
    background: #050505 !important;
    border-color: __GREEN__ !important;
    box-shadow: 7px 7px 0 #050505, 0 0 0 2px __GREEN__ !important;
    transform: skew(-13deg) rotate(1.2deg) translateX(9px) scale(1.025) !important;
    filter: drop-shadow(0 0 7px rgba(128,220,88,.35));
}
[data-testid="stSidebar"] .stButton button:hover::before,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover::before {
    transform: translateX(0) skew(-20deg);
}
[data-testid="stSidebar"] .stButton button:hover::after,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover::after {
    opacity: 1;
    transform: translate(0,-50%);
}
[data-testid="stSidebar"] .stButton button:hover p,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover p {
    color: #fff !important;
    letter-spacing: 2px;
    transform: skew(13deg) translateX(2px);
    text-shadow: 2px 2px 0 #000;
}
[data-testid="stSidebar"] .stButton button:active,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:active {
    transform: skew(-13deg) scale(.96) translate(3px,3px) !important;
    box-shadow: 1px 1px 0 #050505 !important;
    filter: brightness(1.25);
}
[data-testid="stSidebar"] .stButton button:focus-visible,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:focus-visible {
    outline: 3px dashed __GREEN__ !important;
    outline-offset: 5px;
}

/* Toggles, selects and expanders get the same high-contrast menu language */
[data-testid="stSidebar"] [data-testid="stToggle"] {
    padding: 8px 10px;
    margin: 5px 0 9px;
    background: rgba(0,0,0,.78);
    border-left: 3px solid #fff;
    transition: border-color .2s, transform .2s, background .2s;
}
[data-testid="stSidebar"] [data-testid="stToggle"]:hover {
    border-left-color: __GREEN__;
    background: rgba(0,0,0,.94);
    transform: translateX(5px);
}
[data-testid="stSidebar"] [data-testid="stToggle"] label,
[data-testid="stSidebar"] [data-testid="stCheckbox"] label {
    color: #fff !important;
    font-weight: 800 !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div,
[data-testid="stSidebar"] [data-testid="stFileUploader"] section,
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: rgba(0,0,0,.88) !important;
    color: #fff !important;
    border: 2px solid #fff !important;
    border-radius: 0 !important;
    box-shadow: 4px 4px 0 rgba(0,0,0,.65);
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-family: "Arial Black", Impact, sans-serif;
    letter-spacing: 1px;
    text-transform: uppercase;
}
[data-testid="stSidebar"] [data-testid="stExpander"]:hover {
    border-color: __GREEN__ !important;
    transform: translateX(3px);
    transition: transform .18s ease, border-color .18s ease;
}
[data-testid="stSidebar"] [data-testid="stProgress"] > div {
    background: rgba(0,0,0,.7) !important;
    border: 2px solid #fff;
    border-radius: 0 !important;
    padding: 2px;
}
[data-testid="stSidebar"] [data-testid="stProgress"] > div > div {
    background: repeating-linear-gradient(135deg, __GREEN__ 0 8px, #4f9c35 8px 13px) !important;
    background-size: 22px 22px;
    animation: progressRun .7s linear infinite;
}
@keyframes progressRun { to { background-position: 22px 0; } }

/* Capri's portrait has a living idle animation */
.side-card {
    position: relative;
    width: 170px;
    border: 4px solid #000;
    box-shadow: 6px 6px 0 #fff;
    margin: 10px auto 25px;
    background: #000;
    transform: skew(-5deg) rotate(-4deg);
    animation: portraitFloat 4s ease-in-out infinite;
    transition: transform .28s cubic-bezier(.2,.8,.2,1), box-shadow .25s;
}
.side-card::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(transparent 48%, rgba(255,255,255,.16) 50%, transparent 53%);
    background-size: 100% 12px;
    opacity: .28;
    animation: portraitScan 5s linear infinite;
}
.side-card:hover {
    transform: skew(-3deg) rotate(0deg) scale(1.045);
    box-shadow: 9px 9px 0 __GREEN__;
}
.side-card img { width: 100%; display: block; }
@keyframes portraitFloat {
    0%,100% { translate: 0 0; }
    50% { translate: 0 -5px; }
}
@keyframes portraitScan { to { background-position: 0 24px; } }

/* Status panel: moving scanline + sync pulse */
.p5-status-box {
    position: relative;
    overflow: hidden;
    background: #050505;
    border: 3px solid #fff;
    box-shadow: 6px 6px 0 __GREEN__;
    padding: 14px;
    margin-bottom: 20px;
    transform: skew(-8deg) rotate(-1deg);
}
.p5-status-box::after {
    content: "";
    position: absolute;
    inset: -100% 0;
    pointer-events: none;
    background: linear-gradient(transparent, rgba(128,220,88,.15), transparent);
    animation: statusScan 4s linear infinite;
}
@keyframes statusScan { to { transform: translateY(200%); } }
.p5-mood-tag {
    background: __GREEN__;
    color: #000 !important;
    font-family: "Arial Black", Impact, sans-serif;
    font-weight: 900;
    padding: 3px 10px;
    display: inline-block;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
    transform: skew(4deg);
    animation: moodPop 3.8s ease-in-out infinite;
}
@keyframes moodPop { 0%,90%,100% { filter: brightness(1); } 93% { filter: brightness(1.7); } }
.p5-sync-row {
    font-family: "Arial Black", Impact, sans-serif;
    font-size: .95rem;
    color: #fff;
    letter-spacing: 1px;
}

/* Respect reduced-motion preferences */
@media (prefers-reduced-motion: reduce) {
    [data-testid="stSidebar"]::before, .side-card, .side-card::after,
    .p5-status-box::after, .p5-mood-tag,
    [data-testid="stSidebar"] [data-testid="stProgress"] > div > div {
        animation: none !important;
    }
    [data-testid="stSidebar"] .stButton button,
    [data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
        transition: none !important;
    }
}

/* --- CAPRI // EDITORIAL COMMAND LAYER --- */
.capri-side-masthead {
    position: relative;
    margin: 4px 2px 18px;
    padding: 12px 12px 10px;
    color: #fff;
    background: #050505;
    border: 2px solid #fff;
    box-shadow: 6px 6px 0 __GREEN__;
    transform: skew(-5deg) rotate(-1deg);
    overflow: hidden;
}
.capri-side-masthead::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: .22;
    background: repeating-linear-gradient(135deg, transparent 0 9px, #fff 10px 11px, transparent 12px 19px);
    transform: translateX(-65%);
    animation: mastheadSweep 7s ease-in-out infinite;
}
@keyframes mastheadSweep { 0%,65%,100% { transform: translateX(-65%); } 82% { transform: translateX(65%); } }
.capri-side-topline, .capri-side-subline, .capri-side-wordmark { position: relative; z-index: 1; }
.capri-side-topline { display:flex; align-items:center; gap:7px; font: 900 .58rem/1.2 Consolas, monospace; letter-spacing:1.2px; color:#ddd; }
.capri-live-dot { width:7px; height:7px; display:inline-block; border-radius:50%; background:__GREEN__; box-shadow:0 0 9px __GREEN__; animation: liveBlink 1.2s steps(2,end) infinite; }
@keyframes liveBlink { 50% { opacity:.25; } }
.capri-side-wordmark { margin-top:3px; font: 1000 2.65rem/.95 "Arial Black", Impact, sans-serif; letter-spacing:-2px; text-shadow:3px 3px 0 __PINK__; }
.capri-side-wordmark span { color:__GREEN__; animation: cursorBlink 1s steps(2,end) infinite; }
@keyframes cursorBlink { 50% { opacity:0; } }
.capri-side-subline { margin-top:7px; font:800 .55rem/1.3 Consolas, monospace; letter-spacing:1px; color:#bbb; }
.capri-side-subline b { color:__GREEN__; }
.capri-side-rule { height:5px; margin-top:10px; background:__PINK__; transform:skew(-25deg); }
.capri-side-rule i { display:block; width:28%; height:100%; background:__GREEN__; box-shadow:0 0 8px __GREEN__; animation: ruleTravel 2.8s ease-in-out infinite alternate; }
@keyframes ruleTravel { from { margin-left:0; } to { margin-left:72%; } }

/* Portrait becomes a character panel, not a floating thumbnail. */
.side-portrait-stage { position:relative; margin:3px auto 19px; padding:17px 8px 8px; width:100%; }
.side-portrait-stage::before { content:""; position:absolute; inset:5px 13px 19px 4px; border:1px solid rgba(255,255,255,.65); transform:rotate(5deg); pointer-events:none; }
.side-portrait-stage::after { content:""; position:absolute; right:4px; top:17px; width:32px; height:32px; border-top:5px solid __GREEN__; border-right:5px solid __GREEN__; pointer-events:none; }
.side-portrait-stamp { position:relative; z-index:2; width:max-content; margin:0 0 -7px 12px; padding:4px 9px; color:#000; background:__GREEN__; font:900 .62rem/1 "Arial Black",Impact,sans-serif; letter-spacing:1.4px; transform:rotate(-4deg); box-shadow:3px 3px 0 #000; }
.side-portrait-stamp span { color:__PINK__; font-size:.7rem; }
.side-card { z-index:1; width:min(178px,76%); margin:0 auto 7px; border:4px solid #050505; outline:2px solid #fff; box-shadow:8px 8px 0 __PINK__; transform:rotate(-3deg); }
.side-card:hover { transform:rotate(1deg) translateY(-4px) scale(1.035); box-shadow:10px 10px 0 __GREEN__; }
.side-portrait-index { position:relative; z-index:2; width:max-content; margin:8px 5px 0 auto; padding:3px 8px; background:#050505; border-left:3px solid __GREEN__; color:#fff; font:900 .58rem/1.2 Consolas,monospace; letter-spacing:1.3px; transform:skew(-12deg); }
.side-portrait-index b { color:__PINK__; }

/* Make every interactive control respond as one designed interface. */
[data-testid="stSidebar"] [data-testid="stTextInput"] input,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"] {
    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"]:focus-within,
[data-testid="stSidebar"] [data-testid="stSelectbox"]:focus-within {
    transform:translateX(3px);
    filter:drop-shadow(4px 4px 0 rgba(0,0,0,.7));
}
[data-testid="stSidebar"] [data-testid="stTextInput"]:focus-within input,
[data-testid="stSidebar"] [data-testid="stSelectbox"]:focus-within [role="combobox"] {
    border-color:__GREEN__ !important;
    box-shadow:0 0 0 2px #050505, 0 0 0 4px __GREEN__ !important;
}
[data-testid="stSidebar"] [data-testid="stToggle"] [role="switch"] {
    transition:transform .2s cubic-bezier(.2,.8,.2,1), filter .2s ease;
}
[data-testid="stSidebar"] [data-testid="stToggle"]:hover [role="switch"] {
    transform:scale(1.12) rotate(-5deg);
    filter:drop-shadow(0 0 5px __GREEN__);
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    position:relative;
    transition:padding-left .2s ease, color .2s ease;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { padding-left:18px; color:__GREEN__ !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg { transition:transform .22s ease; }
[data-testid="stSidebar"] [data-testid="stExpander"][open] summary svg { transform:rotate(90deg); }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { padding-left:3px; border-left:2px solid rgba(255,255,255,.55); }

/* Less constant movement; keep the punch for actual hover and selection. */
@media (prefers-reduced-motion: reduce) {
    .capri-side-masthead::before, .capri-live-dot, .capri-side-wordmark span,
    .capri-side-rule i { animation:none !important; }
}


/* --- CAPRI // NEON-LIT HARDWARE FINISH ---
/* Keep the Persona angles, but replace flat square slabs with softly cut,
   illuminated surfaces inspired by Capri's luminous green/pink character art. */
:root {
    --capri-green: __GREEN__;
    --capri-pink: __PINK__;
    --capri-cyan: #19e6d2;
}

/* Ambient light pools behind the sidebar instead of a flat red sheet. */
[data-testid="stSidebar"] {
    background:
        radial-gradient(ellipse at 78% 20%, rgba(128,220,88,.24), transparent 34%),
        radial-gradient(ellipse at 12% 76%, rgba(25,230,210,.16), transparent 30%),
        radial-gradient(ellipse at 90% 88%, rgba(255,49,49,.25), transparent 36%),
        repeating-linear-gradient(132deg, transparent 0 28px, rgba(0,0,0,.10) 29px 32px, transparent 33px 58px),
        linear-gradient(145deg, #ff3131 0%, #c90019 58%, #8d0010 100%) !important;
}

/* A soft illuminated rim with a slow moving highlight. */
.capri-side-masthead,
.p5-status-box,
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div,
[data-testid="stSidebar"] [data-testid="stExpander"],
[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    border-radius: 9px !important;
    border: 1px solid rgba(255,255,255,.82) !important;
    box-shadow:
        0 0 0 1px rgba(0,0,0,.9),
        0 0 8px rgba(128,220,88,.42),
        0 0 19px rgba(128,220,88,.18),
        inset 0 0 13px rgba(255,255,255,.045) !important;
    transition: border-color .22s ease, box-shadow .25s ease,
                transform .25s cubic-bezier(.2,.8,.2,1), filter .25s ease !important;
}

/* Thin animated light that travels along the panel edge. */
.capri-side-masthead::after,
.p5-status-box::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    padding: 1px;
    pointer-events: none;
    background: linear-gradient(115deg,
        transparent 4%, rgba(255,255,255,.1) 22%,
        __GREEN__ 42%, #19e6d2 53%, __PINK__ 68%, transparent 88%);
    background-size: 240% 100%;
    animation: capriEdgeLight 5.5s linear infinite;
    opacity: .78;
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
}
@keyframes capriEdgeLight {
    from { background-position: 100% 0; }
    to { background-position: -140% 0; }
}

/* Buttons glow on hover like illuminated controls, not hard paper cut-outs. */
[data-testid="stSidebar"] .stButton button:hover,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover {
    border-color: __GREEN__ !important;
    box-shadow:
        0 0 0 1px #050505,
        0 0 7px __GREEN__,
        0 0 18px rgba(128,220,88,.72),
        0 0 34px rgba(128,220,88,.24),
        inset 0 0 15px rgba(128,220,88,.16) !important;
    filter: brightness(1.12) saturate(1.12);
}

/* Inputs and dropdowns get a soft inner glow when active. */
[data-testid="stSidebar"] [data-testid="stTextInput"]:focus-within,
[data-testid="stSidebar"] [data-testid="stSelectbox"]:focus-within {
    filter: drop-shadow(0 0 7px rgba(128,220,88,.55)) !important;
}
[data-testid="stSidebar"] [data-testid="stTextInput"]:focus-within input,
[data-testid="stSidebar"] [data-testid="stSelectbox"]:focus-within [role="combobox"] {
    border-color: __GREEN__ !important;
    box-shadow: inset 0 0 12px rgba(128,220,88,.15), 0 0 12px rgba(128,220,88,.48) !important;
}

/* Character portrait: luminous aura rather than a plain offset shadow. */
.side-card {
    border-radius: 7px !important;
    border-color: rgba(255,255,255,.92) !important;
    outline: 1px solid rgba(128,220,88,.85) !important;
    box-shadow:
        0 0 0 3px rgba(0,0,0,.92),
        0 0 12px rgba(128,220,88,.65),
        0 0 28px rgba(25,230,210,.25) !important;
}
.side-card:hover {
    box-shadow:
        0 0 0 3px rgba(0,0,0,.92),
        0 0 15px __GREEN__,
        0 0 34px rgba(25,230,210,.48),
        0 0 48px rgba(255,49,49,.2) !important;
}

/* Status panel keeps its slanted silhouette, now with a lit edge. */
.p5-status-box {
    border-color: rgba(255,255,255,.92) !important;
    box-shadow: 0 0 12px rgba(128,220,88,.3),
                0 0 26px rgba(128,220,88,.12),
                inset 0 0 24px rgba(128,220,88,.07) !important;
}

/* Chat area echoes the same illuminated material. */
[data-testid="stChatMessage"] {
    border-radius: 10px !important;
    box-shadow: 0 0 10px rgba(128,220,88,.2),
                inset 0 0 18px rgba(255,255,255,.035) !important;
}
[data-testid="stChatInput"] {
    border-radius: 12px !important;
    box-shadow: 0 0 12px rgba(128,220,88,.32),
                0 0 26px rgba(128,220,88,.12) !important;
}
[data-testid="stChatInput"] > div { border-radius: 9px !important; }

@media (prefers-reduced-motion: reduce) {
    .capri-side-masthead::after, .p5-status-box::before { animation: none !important; }
}

/* --- CAPRI // BOLD LIGHTNING-CUT PANELS ---
   The panel silhouette itself is jagged and substantial; the glow follows
   the whole cut shape instead of being a thin line around a square box. */
:root {
    --capri-zap: #80dc58;
    --capri-zap-cyan: #19e6d2;
    --capri-zap-red: #ff3131;
}

/* Main identity + status become chunky electric plates. */
.capri-side-masthead {
    border-radius: 0 !important;
    clip-path: polygon(
        0 12%, 7% 12%, 5% 0, 100% 0,
        96% 25%, 100% 31%, 94% 100%,
        4% 100%, 7% 76%, 0 70%
    );
    /* Filter outlines follow the clipped silhouette exactly. */
    filter:
        drop-shadow(0 0 1.15px rgba(255,255,255,.98))
        drop-shadow(6px 5px 0 #050505)
        drop-shadow(0 0 7px rgba(128,220,88,.9))
        drop-shadow(0 0 17px rgba(25,230,210,.38));
    padding: 16px 15px 19px !important;
    margin: 8px 5px 24px 2px !important;
    background: linear-gradient(115deg, #050505 0 72%, #171717 72% 100%) !important;
}
.capri-side-masthead::after {
    content: "";
    position: absolute;
    z-index: 0;
    pointer-events: none;
    inset: 0;
    opacity: .25;
    background: linear-gradient(115deg, transparent 0 43%, var(--capri-zap) 44% 47%, transparent 48% 100%);
    clip-path: polygon(0 12%, 7% 12%, 5% 0, 100% 0, 96% 25%, 100% 31%, 94% 100%, 4% 100%, 7% 76%, 0 70%);
}

.p5-status-box {
    border-radius: 0 !important;
    clip-path: polygon(
        0 10%, 8% 10%, 5% 0, 100% 0,
        95% 29%, 100% 36%, 92% 100%,
        0 100%, 5% 66%, 0 59%
    );
    padding: 20px 18px 22px !important;
    margin: 7px 8px 25px 2px !important;
    /* One crisp white edge, generated from the same clipped alpha shape. */
    border: 0 !important;
    filter:
        drop-shadow(0 0 1.25px rgba(255,255,255,.98))
        drop-shadow(7px 6px 0 #050505)
        drop-shadow(0 0 8px rgba(128,220,88,.85))
        drop-shadow(0 0 19px rgba(25,230,210,.32));
    background: linear-gradient(120deg, #050505 0 76%, #101b12 76% 100%) !important;
}
.p5-status-box::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: .22;
    background: linear-gradient(120deg, transparent 0 38%, var(--capri-zap) 39% 43%, transparent 44% 100%);
}
.p5-status-box::after {
    opacity: .8;
    background: linear-gradient(transparent, rgba(128,220,88,.19), transparent);
}

/* Settings controls get matching lightning-cut corners, not tiny rounded cards. */
[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    border-radius: 0 !important;
    clip-path: polygon(0 14%, 7% 14%, 5% 0, 100% 0, 95% 34%, 100% 42%, 94% 100%, 0 100%, 4% 61%, 0 54%);
    border: 0 !important;
    filter: drop-shadow(0 0 1.1px rgba(255,255,255,.98))
            drop-shadow(4px 4px 0 #050505)
            drop-shadow(0 0 5px rgba(128,220,88,.42));
    margin-top: 10px !important;
    margin-bottom: 14px !important;
}
[data-testid="stSidebar"] .stButton button:hover,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover {
    filter: drop-shadow(0 0 1.1px rgba(255,255,255,.98))
            drop-shadow(5px 5px 0 #050505)
            drop-shadow(0 0 8px var(--capri-zap))
            drop-shadow(0 0 17px rgba(128,220,88,.7)) brightness(1.12) !important;
    transform: translateX(5px) skewX(-2deg) !important;
}

[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div,
[data-testid="stSidebar"] [data-testid="stExpander"] {
    border-radius: 0 !important;
    clip-path: polygon(0 12%, 6% 12%, 4% 0, 100% 0, 96% 35%, 100% 43%, 94% 100%, 0 100%, 4% 62%, 0 54%);
    border: 0 !important;
    filter: drop-shadow(0 0 1.1px rgba(255,255,255,.98))
            drop-shadow(4px 4px 0 rgba(0,0,0,.9))
            drop-shadow(0 0 6px rgba(128,220,88,.38));
}
[data-testid="stSidebar"] [data-testid="stTextInput"] input,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"] {
    border-radius: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"]:focus-within,
[data-testid="stSidebar"] [data-testid="stTextInput"]:focus-within {
    filter: drop-shadow(5px 5px 0 #050505)
            drop-shadow(0 0 9px var(--capri-zap)) !important;
}

/* A short, bold electric slash reinforces the shape language in section labels. */
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    border-radius: 0 !important;
    clip-path: polygon(0 12%, 9% 12%, 7% 0, 100% 0, 94% 100%, 0 100%, 4% 54%);
    filter: drop-shadow(0 0 1.1px rgba(255,255,255,.98))
            drop-shadow(4px 4px 0 #050505)
            drop-shadow(0 0 7px rgba(128,220,88,.55));
}

@media (prefers-reduced-motion: reduce) {
    .capri-side-masthead, .p5-status-box,
    [data-testid="stSidebar"] .stButton button {
        transition: none !important;
    }
}


/* --- CAPRI // VOLTAGE UPGRADE ---
   Same lightning-cut language, now charged: a live bolt down the edge,
   lit switches, a bolt-shaped slider, glitching wordmark and zap badge. */

/* a live lightning bolt running down the sidebar's right edge */
[data-testid="stSidebarUserContent"] { position: relative; }
[data-testid="stSidebarUserContent"]::after {
    content: "";
    position: absolute;
    top: 0; bottom: 0; right: 0;
    width: 26px;
    z-index: 0;
    pointer-events: none;
    background: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='220' viewBox='0 0 26 220'%3E%3Cpath d='M13 0 L5 46 L15 50 L6 104 L18 108 L8 166 L16 170 L13 220' fill='none' stroke='%2380dc58' stroke-width='3'/%3E%3Cpath d='M13 0 L5 46 L15 50 L6 104 L18 108 L8 166 L16 170 L13 220' fill='none' stroke='%23ffffff' stroke-width='1'/%3E%3C/svg%3E") repeat-y;
    background-size: 26px 220px;
    filter: drop-shadow(0 0 4px __GREEN__) drop-shadow(0 0 10px rgba(25,230,210,.55));
    opacity: .4;
    animation: boltStrike 6s infinite;
}
@keyframes boltStrike {
    0%, 84%, 100% { opacity: .38; }
    86% { opacity: 1; }
    88% { opacity: .22; }
    90% { opacity: 1; }
    94% { opacity: .5; }
}

/* section labels carry a bolt */
[data-testid="stSidebar"] h2::before,
[data-testid="stSidebar"] h3::before {
    content: "ϟ";
    display: inline-block;
    margin-right: 9px;
    color: __GREEN__;
    text-shadow: 0 0 8px __GREEN__;
    transition: transform .2s cubic-bezier(.2,.8,.2,1);
}
[data-testid="stSidebar"] h2:hover::before,
[data-testid="stSidebar"] h3:hover::before { transform: translateX(4px) scale(1.3); }

/* switches become lightning-cut rows that light up when ON */
[data-testid="stSidebar"] label[data-baseweb="checkbox"] {
    padding: 9px 22px 9px 12px;
    margin: 6px 4px 10px 0;
    background: linear-gradient(100deg, rgba(0,0,0,.88) 0 78%, rgba(0,0,0,.62));
    border-left: 3px solid rgba(255,255,255,.8);
    clip-path: polygon(0 0, 100% 0, 95% 50%, 100% 100%, 0 100%);
    transition: background .28s ease, border-color .22s ease, transform .2s ease;
}
[data-testid="stSidebar"] label[data-baseweb="checkbox"]:hover { transform: translateX(5px); }
[data-testid="stSidebar"] label[data-baseweb="checkbox"]:has(input:checked) {
    background: linear-gradient(100deg, rgba(128,220,88,.34), rgba(0,0,0,.9) 62%);
    border-left-color: __GREEN__;
}

/* meters end in a lightning notch and glow */
[data-testid="stSidebar"] [data-testid="stProgress"] > div {
    box-shadow: 0 0 12px rgba(128,220,88,.45), 4px 4px 0 rgba(0,0,0,.7);
}
[data-testid="stSidebar"] [data-testid="stProgress"] > div > div {
    clip-path: polygon(0 0, 100% 0, calc(100% - 9px) 50%, 100% 100%, 0 100%);
}

/* the slider handle is a little bolt */
[data-testid="stSidebar"] [data-testid="stSlider"] [role="slider"] {
    background: __GREEN__ !important;
    border: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    clip-path: polygon(62% 0, 14% 56%, 46% 56%, 30% 100%, 88% 38%, 56% 38%);
    scale: 1.9;
}
[data-testid="stSidebar"] [data-testid="stSliderThumbValue"] {
    color: #fff !important;
    font-weight: 900 !important;
    text-shadow: 0 0 6px __GREEN__;
}

/* big charged bond number */
.p5-sync-row span { font-size: 1.5rem; text-shadow: 0 0 10px rgba(255,49,49,.9); }

/* wordmark glitches now and then; zap badge pulses */
.capri-side-wordmark { animation: wordGlitch 7s infinite; }
@keyframes wordGlitch {
    0%, 89%, 100% { transform: none; text-shadow: 3px 3px 0 __PINK__; }
    91% { transform: translateX(-3px); text-shadow: -3px 0 #19e6d2, 3px 0 __PINK__; }
    93% { transform: translateX(3px) skewX(-6deg); text-shadow: 3px 0 #19e6d2, -3px 0 __PINK__; }
    95% { transform: none; text-shadow: 3px 3px 0 __PINK__; }
}
.capri-bolt-badge {
    position: absolute;
    right: 14px; top: 9px;
    z-index: 2;
    font: 900 1.7rem/1 "Arial Black", Impact, sans-serif;
    color: __GREEN__;
    text-shadow: 0 0 8px __GREEN__, 0 0 18px #19e6d2;
    animation: badgeZap 3s infinite;
}
@keyframes badgeZap {
    0%, 78%, 100% { opacity: .75; transform: scale(1) rotate(0); }
    83% { opacity: 1; transform: scale(1.4) rotate(-9deg); }
    88% { opacity: .5; transform: scale(1) rotate(0); }
}

/* thin charged scrollbar */
[data-testid="stSidebar"] *::-webkit-scrollbar { width: 8px; }
[data-testid="stSidebar"] *::-webkit-scrollbar-track { background: rgba(0,0,0,.55); }
[data-testid="stSidebar"] *::-webkit-scrollbar-thumb {
    background: linear-gradient(__GREEN__, #19e6d2);
    border: 1px solid #050505;
}

@media (prefers-reduced-motion: reduce) {
    [data-testid="stSidebarUserContent"]::after, .capri-side-wordmark, .capri-bolt-badge { animation: none !important; }
}


/* --- CAPRI // OUTLINE POLISH ---
   Before: the white edge + shadow sat on the same element as the jagged cut,
   so the cut sliced them off. Now the outline is drawn OUTSIDE the cut shape,
   so every plate, button and field has a crisp edge that follows its zigzag. */

/* plates (identity + status): outline lives on a wrapper */
.capri-side-masthead, .p5-status-box { filter: none !important; }
.plate-fx {
    filter: drop-shadow(2px 0 0 #fff) drop-shadow(-2px 0 0 #fff)
            drop-shadow(0 2px 0 #fff) drop-shadow(0 -2px 0 #fff)
            drop-shadow(7px 6px 0 #050505)
            drop-shadow(0 0 10px rgba(128,220,88,.5));
    transition: filter .25s ease;
}
.plate-fx:hover {
    filter: drop-shadow(2px 0 0 __GREEN__) drop-shadow(-2px 0 0 __GREEN__)
            drop-shadow(0 2px 0 __GREEN__) drop-shadow(0 -2px 0 __GREEN__)
            drop-shadow(7px 6px 0 #050505)
            drop-shadow(0 0 16px rgba(128,220,88,.75));
}

/* buttons: outline on the widget wrapper, button itself stays clean */
[data-testid="stSidebar"] .stButton,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] {
    filter: drop-shadow(2px 0 0 #fff) drop-shadow(-2px 0 0 #fff)
            drop-shadow(0 2px 0 #fff) drop-shadow(0 -2px 0 #fff)
            drop-shadow(5px 5px 0 #050505)
            drop-shadow(0 0 7px rgba(128,220,88,.4));
    transition: filter .2s ease;
}
[data-testid="stSidebar"] .stButton:hover,
[data-testid="stSidebar"] [data-testid="stDownloadButton"]:hover {
    filter: drop-shadow(2px 0 0 __GREEN__) drop-shadow(-2px 0 0 __GREEN__)
            drop-shadow(0 2px 0 __GREEN__) drop-shadow(0 -2px 0 __GREEN__)
            drop-shadow(5px 5px 0 #050505)
            drop-shadow(0 0 14px rgba(128,220,88,.75));
}
[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button { filter: none !important; }

/* section labels: same crisp edge, from their wrapper */
[data-testid="stSidebar"] [data-testid="stHeading"] {
    filter: drop-shadow(2px 0 0 #fff) drop-shadow(-2px 0 0 #fff)
            drop-shadow(0 2px 0 #fff) drop-shadow(0 -2px 0 #fff)
            drop-shadow(4px 4px 0 #050505)
            drop-shadow(0 0 6px rgba(128,220,88,.45));
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    filter: none !important;
    border: 0 !important;
}

/* fields, dropdowns, expanders and switches: outline layer sits behind the content */
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div,
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div,
[data-testid="stSidebar"] [data-testid="stExpander"],
[data-testid="stSidebar"] label[data-baseweb="checkbox"] {
    position: relative;
    isolation: isolate;
    clip-path: none !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    filter: drop-shadow(4px 4px 0 #050505) drop-shadow(0 0 6px rgba(128,220,88,.35)) !important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div::before,
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div::before,
[data-testid="stSidebar"] [data-testid="stExpander"]::before,
[data-testid="stSidebar"] label[data-baseweb="checkbox"]::before {
    content: "";
    position: absolute;
    inset: -2px;
    z-index: -1;
    background: #fff;
    clip-path: polygon(0 12%, 6% 12%, 4% 0, 100% 0, 96% 35%, 100% 43%, 94% 100%, 0 100%, 4% 62%, 0 54%);
    transition: background .2s ease;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div::after,
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div::after,
[data-testid="stSidebar"] [data-testid="stExpander"]::after,
[data-testid="stSidebar"] label[data-baseweb="checkbox"]::after {
    content: "";
    position: absolute;
    inset: 0;
    z-index: -1;
    background: linear-gradient(105deg, #0b0b0b 0 70%, #151a15);
    clip-path: polygon(0 12%, 6% 12%, 4% 0, 100% 0, 96% 35%, 100% 43%, 94% 100%, 0 100%, 4% 62%, 0 54%);
    transition: background .25s ease;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div:hover::before,
[data-testid="stSidebar"] [data-testid="stExpander"]:hover::before,
[data-testid="stSidebar"] label[data-baseweb="checkbox"]:hover::before,
[data-testid="stSidebar"] [data-testid="stTextInput"] > div > div:focus-within::before,
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div:focus-within::before { background: __GREEN__; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"] { padding: 9px 24px 9px 14px; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"]:has(input:checked)::before { background: __GREEN__; }
[data-testid="stSidebar"] label[data-baseweb="checkbox"]:has(input:checked)::after {
    background: linear-gradient(105deg, #1c3a12, #0b0b0b 68%);
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
                     "__PFLASH__": str(p_flash),
                     "__PSLASHIN__": str(p_slash_in),
                     "__PSLASHHOLD__": str(p_slash_hold),
                     "__PWIPEEND__": str(p_wipe_end),
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
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M).replace("[ASK]", "")
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


# ---------- your voice -> text (speech to text, done by gemini) ----------
def transcribe(audio_bytes):
    """Turns a recording of you talking into text. Returns '' if it fails."""
    try:
        reply = client.models.generate_content(
            model=MODELS[0],
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                "Transcribe this speech exactly as spoken, in the language spoken. "
                "Output only the words, nothing else. If there is no speech, output nothing.",
            ],
        )
        return (reply.text or "").strip()
    except Exception as e:
        st.warning("couldn't hear that (" + str(e)[:80] + "), try again")
        return ""


def speak_edge(text):
    if not HAVE_EDGE:
        st.error("voice needs: py -m pip install edge-tts")
        return
    async def _generate():
        # en-US-AriaNeural suaranya dewasa, alami, dan enerjik
        voice = st.session_state.get("edge_voice", "en-US-JennyNeural")
        rate = "%+d%%" % st.session_state.get("edge_rate", 10)
        pitch = "%+dHz" % st.session_state.get("edge_pitch", 5)
        communicate = edge_tts.Communicate(clean_for_voice(text), voice,
                                           rate=rate, pitch=pitch)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data

    try:
        audio_bytes = asyncio.run(_generate())
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
    except Exception as e:
        st.error(f"Voice error: {e}")

# ---------- capri's cloned voice (runs on YOUR computer, unlimited, no quota) ----------
REF_VOICE_FILE = os.path.join(HERE, "capri_ref.wav")   # 10-30s clean clip of the voice


@st.cache_resource(show_spinner="loading capri's voice model (first time downloads ~2GB)...")
def load_xtts():
    import torch
    from TTS.api import TTS
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)


def speak_clone(text):
    if not os.path.exists(REF_VOICE_FILE):
        st.error("put capri_ref.wav next to capri_app.py")
        return False
    try:
        model = load_xtts()
        samples = model.tts(text=clean_for_voice(text), speaker_wav=REF_VOICE_FILE,
                            language="en")
        pcm = (np.clip(np.array(samples), -1, 1) * 32767).astype(np.int16).tobytes()
        st.audio(pcm_to_wav(pcm, 24000), format="audio/wav", autoplay=True)
        return True
    except Exception as e:
        st.error("cloned voice failed (" + str(e)[:120] + "), using the preset voice")
        return False


def speak_voice(text):
    if st.session_state.get("voice_engine", "").startswith("capri clone"):
        if speak_clone(text):
            return
    speak_edge(text)


def boot_overlay_html():
    lines = "".join(
        '<div class="boot-line bl%d">%s</div>' % (i, htmllib.escape(line))
        for i, line in enumerate(BOOT_LINES)
    )
    char = ""
    slash_face = ""
    if char_b64:
        char = ('<div class="boot-char"><img src="data:image/png;base64,'
                + char_b64 + '"></div>')
        slash_face = ('<img class="p5-slash-face" src="data:image/png;base64,'
                      + char_b64 + '">')
    return (
        '<div class="boot-overlay">'
        '<div class="boot-bg-top"></div>'
        '<div class="boot-bg-bot"></div>'
        '<div class="p5-slash-flash"></div>'
        '<div class="p5-slash-bar">'
        + slash_face +
        '<div class="p5-slash-text-wrap">'
        '<div class="p5-slash-kicker">NEURAL LINK // SYNCHRONIZED</div>'
        '<div class="p5-slash-text">CAPRI ONLINE</div>'
        '</div></div>'
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




_BGM_CONTROLLER = r"""
(function () {
  window.__capriBgmVer = 3;
  var D = document, W = window;
  var legacy = D.getElementById('capri-bgm');
  if (legacy) { legacy.pause(); legacy.remove(); }
  W.capriBgm = function (want, vol, tracks, mood, delayMs, fadeMs) {
    var S = W.__bgm = W.__bgm || { tracks: {}, cur: null, name: null, bound: false };
    var k;
    for (k in tracks) { S.tracks[k] = tracks[k]; }
    S.vol = Math.max(0, Math.min(1, vol));
    S.want = !!want;
    function fade(el, to, ms, done) {
      clearInterval(el._f);
      var from = el.volume, t0 = Date.now();
      el._f = setInterval(function () {
        var p = Math.min(1, (Date.now() - t0) / ms);
        el.volume = Math.max(0, Math.min(1, from + (to - from) * p));
        if (p >= 1) { clearInterval(el._f); if (done) { done(); } }
      }, 50);
    }
    function kill(el) { if (!el) { return; } clearInterval(el._f); el.pause(); el.remove(); }
    if (!S.want) {
      kill(S.cur); S.cur = null; S.name = null;
      Array.prototype.forEach.call(D.querySelectorAll('audio.capri-bgm'), kill);
      return;
    }
    if (mood && S.tracks[mood] && S.name !== mood) {
      var el = D.createElement('audio');
      el.className = 'capri-bgm'; el.loop = true; el.src = S.tracks[mood]; el.volume = 0;
      D.body.appendChild(el);
      var prev = S.cur; S.cur = el; S.name = mood;
      var delayMs = (arguments[4] || 0);
      var fadeMs = (arguments[5] || 2800);
      S.waitingDelay = delayMs > 0;
      setTimeout(function () {
        S.waitingDelay = false;
        if (S.cur !== el || !S.want) { return; }
        el.play().catch(function () {});
        fade(el, S.vol, fadeMs);
      }, delayMs);
      if (prev) { fade(prev, 0, 1600, function () { kill(prev); }); }
    } else if (S.cur) {
      fade(S.cur, S.vol, 250);
    }
    if (!S.bound) {
      S.bound = true;
      ['click', 'keydown', 'touchstart'].forEach(function (t) {
        D.addEventListener(t, function () {
          if (S.cur && S.cur.paused && S.want && !S.waitingDelay) { S.cur.play().catch(function () {}); }
        }, true);
      });
    }
    if (S.cur && S.cur.paused) { S.cur.play().catch(function () {}); }
  };
})();
"""
_BGM_MIME = {".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".wav": "audio/wav", ".m4a": "audio/mp4"}


def _find_track(name):
    for e in _BGM_MIME:
        p = os.path.join(HERE, "capri_" + name + e)
        if os.path.exists(p):
            return p
    return None


_MOOD_RE = {
    "danger": re.compile(r"\b(scared|afraid|danger|careful|hide|alarm|uh-?oh|they'?re coming|trace|angry|furious|ugh|annoyed|how dare|shut up|leave me alone)\b"),
    "sweet": re.compile(r"(\b(love|miss(ed)? you|sweet|cute|thank(s| you)|hug|cuddle|adore|aww+|proud of you|glad you|stay with me)\b|❤|💕|💗)"),
    "happy": re.compile(r"(haha|hehe|lol|😏|\bteas(e|ing)\b|\bsilly\b|giggle)"),
    "curious": re.compile(r"(\?|\b(why|how|hmm+|wonder|think|thinking|what if|tell me)\b)"),
}


def get_music_mood(bond, history):
    """sweet / happy / curious / danger / home, from her bond and her latest reply."""
    h = st.session_state.get("hack")
    if h and h.get("active") and h.get("alert", 0) >= 70:
        return "danger"                                   # the hack is going badly
    last = ""
    for m in reversed(history):
        if m["role"] == "assistant":
            last = re.sub(r"^\s*//.*$", "", m["text"], flags=re.M).replace("[ASK]", "").lower()
            break
    if bond < 30 or _MOOD_RE["danger"].search(last):
        return "danger"
    if bond >= 80 or _MOOD_RE["sweet"].search(last):
        return "sweet"
    if _MOOD_RE["happy"].search(last):
        return "happy"
    if _MOOD_RE["curious"].search(last):
        return "curious"
    return "home"


def pick_music_mood():
    """Same as above, but calm moods wait 25s before switching so it never flickers."""
    want = get_music_mood(st.session_state.bond_level, st.session_state.history)
    cur = st.session_state.get("music_mood")
    now = time.time()
    if want != cur and (cur is None or want == "danger"
                        or now - st.session_state.get("music_mood_since", 0) >= 25):
        st.session_state.music_mood = want
        st.session_state.music_mood_since = now
    return st.session_state.get("music_mood", want)




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
if "mem_pending" not in st.session_state:
    st.session_state.mem_pending = []
if "mem_due" not in st.session_state:
    st.session_state.mem_due = False
if "bond_level" not in st.session_state:
    st.session_state.bond_level = 50
if "hack" not in st.session_state:
    st.session_state.hack = {"active": False, "log": []}



def inject_home_music(on, vol, mood="home", delay_ms=0, fade_ms=3200):
    """Plays / crossfades the mood music. Returns the track name, or None if no music files."""
    name = mood if _find_track(mood) else "home"
    path = _find_track(name)
    if not path:
        return None
    if "bgm_sent_tracks" not in st.session_state:
        st.session_state.bgm_sent_tracks = []
    tracks = {}
    if on and name not in st.session_state.bgm_sent_tracks:      # each file is only sent once
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        tracks[name] = "data:%s;base64,%s" % (_BGM_MIME[os.path.splitext(path)[1]], data)
        st.session_state.bgm_sent_tracks.append(name)
    if not on:
        st.session_state.bgm_sent_tracks = []                   # off/on again = a fresh start
    html = ("<script>try{var P=window.parent,D=P.document;"
            "if(P.__capriBgmVer!==3){var s=D.createElement('script');s.textContent="
            + json.dumps(_BGM_CONTROLLER) + ";D.head.appendChild(s);}"
            "P.capriBgm(" + ("true" if on else "false") + "," + str(vol / 100.0) + ","
            + json.dumps(tracks) + "," + json.dumps(name) + ","
            + str(int(delay_ms)) + "," + str(int(fade_ms)) + ");}catch(e){}</script>")
    components.html(html, height=0)
    return name


# ---------- being nice or mean changes the bond (and so the music) ----------
_MEAN_RE = re.compile(r"\b(shut up|stupid|idiot|hate you|useless|dumb|ugly|annoying|go away|trash|loser)\b")
_NICE_RE = re.compile(r"\b(love you|thank you|thanks|miss you|proud of you|you'?re sweet|good job|cute|best friend|glad you)\b")


def bond_change(msg):
    t = msg.lower()
    if _MEAN_RE.search(t):
        return -6
    if _NICE_RE.search(t):
        return 2
    return 1


voice_status_box = None
mic_text = None
rec = None
diary_req = False



if BOOT_SCREEN and not st.session_state.booted:
    st.session_state.booted = True
    if is_fresh_visit():
        try:
            st.query_params["intro"] = str(round(time.time(), 1))
        except Exception:
            pass
        st.session_state.just_booted_bgm = True
        overlay_box = st.empty()
        overlay_box.markdown(boot_overlay_html(), unsafe_allow_html=True)
        if st.session_state.get("music_on", True):
            _slash_delay_ms = int((reveal_s + hold_s) * 1000)
            inject_home_music(True, st.session_state.get("music_vol", 25),
                              pick_music_mood(), delay_ms=_slash_delay_ms, fade_ms=3400)
        time.sleep(total_s + 0.2)
        overlay_box.empty()
st.session_state.booted = True

photo = None
watch_on = False
voice_on = False
# ---------- mood music: five loops that crossfade with how she feels ----------
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
    st.markdown(
        """
        <div class="plate-fx"><div class="capri-side-masthead">
            <div class="capri-bolt-badge">ϟ</div>
            <div class="capri-side-topline"><span>NEURAL SLOT // 01</span><span class="capri-live-dot"></span><span>ONLINE</span></div>
            <div class="capri-side-wordmark">CAPRI<span>_</span></div>
            <div class="capri-side-subline">PERSONALITY CONSTRUCT <b>·</b> HOST LINK ACTIVE</div>
            <div class="capri-side-rule"><i></i></div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )
    user_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.getenv("GEMINI_API_KEY", ""),
        placeholder="Paste your AIza... key here"
    )

    if avatar_card_b64:
        st.markdown(
            '<div class="side-portrait-stage">'
            '<div class="side-portrait-stamp">LIVE FEED <span>●</span></div>'
            '<div class="side-card"><img src="data:image/png;base64,'
            + avatar_card_b64 + '"></div>'
            '<div class="side-portrait-index">FIG. 01 <b>//</b> CAPRI</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.header("construct status")
        current_mood, mood_color = get_capri_mood(st.session_state.bond_level, st.session_state.history)
        st.markdown(
        f"""
        <div class="plate-fx"><div class="p5-status-box">
            <div class="p5-mood-tag" style="background:{mood_color};">{current_mood}</div>
            <div class="p5-sync-row">NEURAL BOND SYNC // <span style="color:{PINK};">{st.session_state.bond_level}%</span></div>
        </div></div>
        """,
        unsafe_allow_html=True,
    )
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

    music_on = st.toggle("home music", value=True, key="music_on")
    music_vol = 25
    if music_on:
        music_vol = st.slider("music volume", 0, 100, 25, key="music_vol")
    _fade_duration = 3400 if st.session_state.pop("just_booted_bgm", False) else 2600
    _playing = inject_home_music(music_on, music_vol, pick_music_mood(), delay_ms=0, fade_ms=_fade_duration)
    if not _playing:
        st.caption("put capri_home.mp3 (plus capri_sweet / happy / curious / danger .mp3) next to capri_app.py")
    elif music_on:
        st.caption("♪ now playing: " + _playing + " · starts after your first click")

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

    with st.expander("things she tried through you"):
        _firsts = load_firsts()
        if _firsts:
            for f in reversed(_firsts[-15:]):
                st.text("• " + f.get("what", "") + "  (" + f.get("date", "") + ")")
        else:
            st.caption("nothing yet. tell her about food, music, weather, places...")

    with st.expander("capri's diary"):
        if st.button("write today's entry", key="diary_btn"):
            diary_req = True
        _diary = load_diary()
        if _diary:
            for _day in sorted(_diary, reverse=True)[:7]:
                st.markdown("**" + _day + "**")
                st.write(_diary[_day])
        else:
            st.caption("she hasn't written anything yet. chat a bit, then press the button.")

    chat_lines = [("you" if m["role"] == "user" else "capri") + ": " + m["text"]
                  for m in st.session_state.history]
    st.download_button(
        "save chat (.txt)",
        data="\n\n".join(chat_lines) or "(empty chat)",
        file_name="capri_chat_" + datetime.now().strftime("%Y%m%d_%H%M") + ".txt",
        mime="text/plain",
    )

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
if mic_on and rec is not None:
    with st.spinner("listening..."):
        mic_text = transcribe(rec.getvalue())
    st.session_state.mic_key += 1   # fresh recorder, so this clip is never re-sent

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
    st.session_state.history.append(
        {"role": "assistant", "text": missed_you_message() or pick_greeting()})
    st.session_state.play_blip = True
st.session_state.greeted = True


_FACE_RULES = [   # (picture file, words that trigger it) - checked in this order
    ("capri_scared.png", r"\b(scared|afraid|danger|careful|hide|alarm|uh-?oh|they'?re coming|trace|run)\b"),
    ("capri_angry.png", r"\b(angry|furious|mad|ugh|annoyed|how dare|i hate|shut up)\b"),
    ("capri_sleepy.png", r"\b(sleepy|tired|yawn|zzz+|goodnight|good night|nap|exhausted|bed)\b"),
]


def get_dynamic_avatar(text):
    t = text.lower()
    for fname, pattern in _FACE_RULES:       # new moods only show if the picture exists
        path = os.path.join(HERE, fname)
        if os.path.exists(path) and re.search(pattern, t):
            return path
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


FRAG_RE = re.compile(r"^\s*//\s*(.+)$", re.M)


def split_reply(text):
    """-> (what she says, the other voice's line or None)"""
    t = text.replace("[ASK]", "")
    frags = FRAG_RE.findall(t)
    main = FRAG_RE.sub("", t).strip()
    return (main or t.strip()), (" ".join(f.strip() for f in frags) if frags else None)


def show_message(i, m):
    if m["role"] == "user":
        with st.chat_message("user", avatar=USER_AVATAR):
            if m.get("image"):
                st.image(m["image"], width=240)
            st.write(m["text"])
    else:
        main, frag = split_reply(m["text"])
        avatar_to_use = get_dynamic_avatar(main)
        with st.container(key=f"capri_{i}"):
            with st.chat_message("assistant", avatar=avatar_to_use):
                st.write(main)
                if frag:
                    st.caption("// " + frag)


for i, m in enumerate(st.session_state.history):
    show_message(i, m)

# she asked permission for something dangerous -> answer with a tap
_hist = st.session_state.history
if (_hist and _hist[-1]["role"] == "assistant" and "[ASK]" in _hist[-1]["text"]
        and not st.session_state.get("quick_reply")):
    _c1, _c2, _c3 = st.columns(3)
    if _c1.button("yes, go for it", key="ask_yes"):
        st.session_state.quick_reply = "(yes, go for it)"
        st.rerun()
    if _c2.button("no, wait!", key="ask_no"):
        st.session_state.quick_reply = "(no, wait! don't)"
        st.rerun()
    if _c3.button("surprise me", key="ask_any"):
        st.session_state.quick_reply = "(do whatever you want, surprise me)"
        st.rerun()


HACK_TARGETS = [
    "the megacorp vault under the noodle district",
    "every traffic light on the main strip",
    "a rooftop billboard network",
    "the vending machine empire",
    "the city's neon sign grid",
]
HACK_MAX_TURNS = 15


def run_hack(cmd):
    h = st.session_state.hack
    prompt = (
        "You are Capri, a chaotic, playful digital construct, narrating a tiny pretend text game "
        "where your host 'hacks' a fictional target. It is pure fiction: never give real hacking "
        "steps, tools or code. Target: %s. Breach progress: %d/100. Alert level: %d/100. "
        "Turn %d of %d.\nRecent log:\n%s\n\nThe host typed this command: \"%s\"\n\n"
        "Narrate what happens in one or two short sentences in your own voice (texting style, "
        "a little weird, no asterisks). Smart or creative commands raise progress; reckless or "
        "silly ones raise the alert. Return ONLY JSON like "
        "{\"narration\": \"...\", \"progress_delta\": 15, \"alert_delta\": 5} with progress_delta "
        "from -10 to 30 and alert_delta from 0 to 35."
        % (h["target"], h["progress"], h["alert"], h["turns"] + 1, HACK_MAX_TURNS,
           "\n".join(h["log"][-6:]), cmd.replace('"', "'"))
    )
    reply = client.models.generate_content(
        model=st.session_state.get("model_pick", MODELS[0]),
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=300, response_mime_type="application/json"),
    )
    data = json.loads(reply.text or "{}")
    if not isinstance(data, dict):
        data = {}
    try:
        dp = max(-10, min(30, int(data.get("progress_delta", 8))))
        da = max(0, min(35, int(data.get("alert_delta", 5))))
    except Exception:
        dp, da = 8, 5
    h["progress"] = max(0, min(100, h["progress"] + dp))
    h["alert"] = max(0, min(100, h["alert"] + da))
    h["turns"] += 1
    h["log"].append("> " + cmd)
    h["log"].append("capri: " + str(data.get("narration", "...static...")).strip()[:300])
    if h["progress"] >= 100:
        h["active"] = False
        h["log"].append("> BREACH COMPLETE. capri: we did it!! hehe")
        st.session_state.bond_level = min(100, st.session_state.bond_level + 5)
    elif h["alert"] >= 100 or h["turns"] >= HACK_MAX_TURNS:
        h["active"] = False
        h["log"].append("> TRACE COMPLETE. capri: run run run, they found us!")


HACK_CSS = """
<style>
.hk{position:relative;background:#020202;border:3px solid __GREEN__;box-shadow:0 0 18px __GREEN__55, inset 0 0 40px #000;font-family:Consolas,"Courier New",monospace;color:#d8ffd0;padding:0 0 12px;overflow:hidden;margin-bottom:10px}
.hk.hot{border-color:__PINK__;box-shadow:0 0 22px __PINK__99, inset 0 0 40px #000;animation:hkpulse .9s infinite}
.hk::after{content:"";position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(255,255,255,.035) 0 1px,transparent 1px 3px)}
.hk-top{display:flex;justify-content:space-between;align-items:center;background:__GREEN__;color:#000;font-weight:900;padding:4px 10px;font-size:.8rem;letter-spacing:.12em}
.hk.hot .hk-top{background:__PINK__}
.hk-live::before{content:"●";margin-right:6px;animation:hkblink 1s steps(2) infinite}
.hk-title{display:inline-block;margin:12px 12px 6px;padding:4px 16px;border:4px double __GREEN__;color:__GREEN__;text-shadow:2px 0 __PINK__,-2px 0 #50b4ff;font-size:.9rem;font-weight:900;letter-spacing:.12em;white-space:nowrap}
.hk.hot .hk-title{border-color:__PINK__;color:__PINK__;text-shadow:2px 0 __GREEN__,-2px 0 #50b4ff}
.hk-target{padding:2px 12px 8px;color:#9fe8ff;font-size:.85rem}
.hk-meters{padding:0 12px}
.hk-m{margin:5px 0}
.hk-lab{display:flex;justify-content:space-between;font-size:.72rem;letter-spacing:.14em;font-weight:900}
.hk-bar{position:relative;height:14px;background:#0b0b0b;border:1px solid #333}
.hk-fill{height:100%;transition:width .6s}
.hk-g{background:linear-gradient(90deg,#2d7a1a,__GREEN__);box-shadow:0 0 10px __GREEN__}
.hk-r{background:linear-gradient(90deg,#8a0f0f,__PINK__);box-shadow:0 0 10px __PINK__}
.hk-bar::after{content:"";position:absolute;inset:0;background:repeating-linear-gradient(90deg,transparent 0 9px,#000 9px 11px)}
.hk-warn{color:__PINK__;text-align:center;font-weight:900;letter-spacing:.2em;font-size:.8rem;margin:8px 0 0;animation:hkblink .6s steps(2) infinite}
.hk-log{margin:10px 12px 0;padding:8px 10px;background:#000;border:1px solid #1f3a1a}
.hk-line{margin:3px 0;font-size:.88rem;line-height:1.35;word-break:break-word}
.hk-cmd{color:#50b4ff}
.hk-prompt{color:__GREEN__;margin-right:6px}
.hk-capri{color:#fff}
.hk-tag{background:__PINK__;color:#000;font-weight:900;font-size:.7rem;padding:0 5px;margin-right:6px}
.hk-sys{color:__GREEN__;text-shadow:0 0 6px __GREEN__}
.hk-bad{color:__PINK__;text-shadow:0 0 6px __PINK__}
.hk-dim{color:#777}
.hk-new{animation:hkin .5s ease-out}
.hk-cur::after{content:"█";color:__GREEN__;animation:hkblink 1s steps(2) infinite}
.hk-banner{margin:10px 12px 0;padding:8px;text-align:center;font-weight:900;letter-spacing:.25em;font-size:1.05rem;color:#000}
.hk-win{background:__GREEN__;animation:hkglitch .25s 3}
.hk-lose{background:__PINK__;animation:hkshake .4s 3}
@keyframes hkblink{50%{opacity:0}}
@keyframes hkpulse{50%{box-shadow:0 0 6px __PINK__55, inset 0 0 40px #000}}
@keyframes hkin{from{opacity:0;transform:translateX(-10px);filter:blur(2px)}to{opacity:1;transform:none;filter:none}}
@keyframes hkshake{25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}
@keyframes hkglitch{33%{transform:translateX(4px);text-shadow:-3px 0 #50b4ff}66%{transform:translateX(-4px);text-shadow:3px 0 __PINK__}}
</style>
"""
HACK_CSS = "".join(l.strip() for l in HACK_CSS.splitlines()).replace("__GREEN__", GREEN).replace("__PINK__", PINK)

HACK_TITLE = ("╔═══════════════════════════════╗\n"
              "║  C A P R I  //  B R E A C H   ║\n"
              "╚═══════════════════════════════╝")


def hack_panel_html(h):
    e = htmllib.escape
    log = h.get("log", [])
    active = bool(h.get("active"))
    prog, alert = int(h.get("progress", 0)), int(h.get("alert", 0))
    last = log[-1] if log else ""
    hot = active and alert >= 70
    right = ("TURN %d/%d" % (h.get("turns", 0), HACK_MAX_TURNS)) if active else ""
    out = ['<div class="hk%s">' % (" hot" if hot else ""),
           '<div class="hk-top"><span class="hk-live">%s</span><span>%s</span></div>'
           % ("LIVE" if active else ("BREACHED" if last.startswith("> BREACH")
                                     else "TRACED" if last.startswith("> TRACE") else "STANDBY"), right),
           '<div class="hk-title">C A P R I &nbsp;//&nbsp; B R E A C H</div>']
    if h.get("target"):
        out.append('<div class="hk-target">TARGET &gt; %s</div>' % e(h["target"]))
    if active or h.get("target"):
        out.append('<div class="hk-meters">'
                   '<div class="hk-m"><div class="hk-lab"><span>BREACH</span><span>%d%%</span></div>'
                   '<div class="hk-bar"><div class="hk-fill hk-g" style="width:%d%%"></div></div></div>'
                   '<div class="hk-m"><div class="hk-lab"><span>ALERT</span><span>%d%%</span></div>'
                   '<div class="hk-bar"><div class="hk-fill hk-r" style="width:%d%%"></div></div></div>'
                   '</div>' % (prog, prog, alert, alert))
    if hot:
        out.append('<div class="hk-warn">⚠ TRACE CLOSING IN ⚠</div>')
    if log:
        rows = []
        shown = log[-10:]
        for idx, line in enumerate(shown):
            new = " hk-new" if idx >= len(shown) - 2 else ""
            t = e(line)
            if line.startswith("capri:"):
                rows.append('<div class="hk-line hk-capri%s"><span class="hk-tag">CAPRI</span>%s</div>'
                            % (new, t[6:].strip()))
            elif line.startswith("> TRACE"):
                rows.append('<div class="hk-line hk-bad%s">%s</div>' % (new, t))
            elif line.startswith("> BREACH") or line.startswith("> target"):
                rows.append('<div class="hk-line hk-sys%s">%s</div>' % (new, t))
            elif line.startswith("> you pulled"):
                rows.append('<div class="hk-line hk-dim">%s</div>' % t)
            elif line.startswith("> "):
                rows.append('<div class="hk-line hk-cmd%s"><span class="hk-prompt">&gt;</span>%s</div>'
                            % (new, e(line[2:])))
            else:
                rows.append('<div class="hk-line">%s</div>' % t)
        if active:
            rows.append('<div class="hk-line hk-cur"></div>')
        out.append('<div class="hk-log">%s</div>' % "".join(rows))
    if last.startswith("> BREACH"):
        out.append('<div class="hk-banner hk-win">ACCESS GRANTED</div>')
    elif last.startswith("> TRACE"):
        out.append('<div class="hk-banner hk-lose">CONNECTION LOST</div>')
    out.append("</div>")
    return HACK_CSS + "".join(out)


with st.expander("hack the mainframe (mini game)"):
    _h = st.session_state.hack
    st.markdown(hack_panel_html(_h), unsafe_allow_html=True)
    if _h["active"]:
        with st.form("hack_form", clear_on_submit=True):
            _cmd = st.text_input("command", placeholder="scan, ping the guards, sneak in, ...")
            _go = st.form_submit_button("run")
        if _go and _cmd.strip():
            with st.spinner("capri is typing..."):
                try:
                    run_hack(_cmd.strip()[:80])
                except Exception as e:
                    st.warning("static on the line (" + str(e)[:80] + "), try again")
                else:
                    st.session_state.play_blip = True
                    st.rerun()
        if st.button("give up", key="hack_quit"):
            st.session_state.hack = {"active": False, "log": _h["log"] + ["> you pulled the plug."]}
            st.rerun()
    else:
        st.caption("type commands and she narrates what happens. win by breaching "
                   "before the alert fills up. winning gives a little bond boost.")
        if st.button("start a new hack", key="hack_start"):
            _target = random.choice(HACK_TARGETS)
            st.session_state.hack = {
                "active": True, "target": _target, "progress": 0, "alert": 0, "turns": 0,
                "log": ["> target locked: " + _target,
                        "capri: i'm in your head. type commands and i'll narrate. try 'scan'!"],
            }
            st.rerun()


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
if not user and st.session_state.get("quick_reply"):
    user = st.session_state.pop("quick_reply")
if user:
    entry = {"role": "user", "text": user}
    if photo is not None:
        entry["image"] = photo.getvalue()
        entry["mime"] = photo.type or "image/jpeg"
    st.session_state.history.append(entry)
    save_last_seen(time.time())

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
        
        if len(user.split()) >= 3:
            st.session_state.mem_pending.append(user)
            if len(st.session_state.mem_pending) >= MEM_EVERY:
                st.session_state.mem_due = True

    except Exception as e:
        typing_box.empty()
        st.session_state.history.pop()
        st.error(f"error: {e}")
        st.stop()
    typing_box.empty()

    st.session_state.bond_level = min(100, max(0, st.session_state.bond_level + bond_change(user)))

    st.session_state.history.append({"role": "assistant", "text": text})
    st.session_state.cam_key += 1
    st.session_state.play_blip = True
    st.session_state.speak_text = text
    st.rerun()


speak_text = st.session_state.pop("speak_text", None)
if st.session_state.play_blip:
    st.session_state.play_blip = False
    if voice_on and speak_text:
        speak_voice(speak_text)
    elif sound_on:
        try:
            st.audio(make_blip(), format="audio/wav", autoplay=True)
        except Exception:
            pass

if st.session_state.mem_due:
    st.session_state.mem_due = False
    batch = st.session_state.mem_pending[-MEM_EVERY * 2:]
    st.session_state.mem_pending = []
    try:
        update_memories(batch)
    except Exception:
        pass        # memory is a bonus, never break the chat for it


def write_diary():
    hist = list(st.session_state.history)[-30:]
    convo = "\n".join(
        ("host: " if m["role"] == "user" else "you: ") + split_reply(m["text"])[0]
        for m in hist)
    reply = client.models.generate_content(
        model=st.session_state.get("model_pick", MODELS[0]),
        contents=("Write today's diary entry as Capri, in first person: 3 to 5 short sentences, "
                  "texting style, chaotic and a little weird. No headers, no lines starting with //, "
                  "no [ASK] tag, no asterisks. Write about what you and your host did or talked "
                  "about and how you felt. Today's chat:\n" + convo),
        config=types.GenerateContentConfig(
            system_instruction=get_full_persona(), max_output_tokens=500),
    )
    text = split_reply(reply.text or "")[0].strip()
    if text:
        d = load_diary()
        d[datetime.now().strftime("%Y-%m-%d")] = text
        _write_json(DIARY_FILE, d)
        return True
    return False


if diary_req:
    if not st.session_state.history:
        st.toast("talk to her first, then she has something to write about")
    else:
        _ok = False
        with st.spinner("she's writing..."):
            try:
                _ok = write_diary()
            except Exception as e:
                st.warning("couldn't write it (" + str(e)[:80] + "), try again")
        if _ok:
            st.rerun()


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