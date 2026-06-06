"""
fallback.py — ChatForge Rule-Based Fallback Engine
====================================================
Activated automatically when no API key is configured.

Design principles:
  - Priority-ordered intent matching (most specific first)
  - Response rotation so repeated questions don't feel robotic
  - Regex patterns for flexible phrase recognition
  - Every code-path returns a non-empty string — never crashes
  - Zero external dependencies — fully offline, always available
"""

import re
import random
from backend.config import (
    BUSINESS_NAME,
    BUSINESS_HOURS,
    BUSINESS_PHONE,
    BUSINESS_ADDRESS,
    BUSINESS_WEBSITE,
    BUSINESS_DESCRIPTION,
)

# ---------------------------------------------------------------------------
# Response rotation helpers
# ---------------------------------------------------------------------------

# Each intent maps to a list of response templates.
# Rotating through them prevents every repeated question feeling identical.
_rotation_counters: dict[str, int] = {}


def _pick(intent_key: str, responses: list[str]) -> str:
    """Round-robin through a list of responses for a given intent key."""
    idx = _rotation_counters.get(intent_key, 0) % len(responses)
    _rotation_counters[intent_key] = idx + 1
    return responses[idx]


def _rand(responses: list[str]) -> str:
    """Pick a random response (for intents like greetings where variety matters)."""
    return random.choice(responses)


# ---------------------------------------------------------------------------
# Intent definitions
# ---------------------------------------------------------------------------
# Each intent is a dict with:
#   "patterns" : list of regex strings — any match triggers this intent
#   "keywords" : list of plain strings — any substring match triggers this intent
#   "key"      : stable string used for rotation tracking
#   "handler"  : callable(msg) -> str
#
# Intents are checked top-to-bottom; first match wins.
# Put more specific intents before more general ones.

def _handle_greeting(msg: str) -> str:
    return _rand([
        f"Hi there! Welcome to {BUSINESS_NAME}. How can I help you today?",
        f"Hello! Thanks for reaching out to {BUSINESS_NAME}. What can I do for you?",
        f"Hey! Great to hear from you. What can {BUSINESS_NAME} help you with?",
        f"Hi! I'm here to help. What would you like to know about {BUSINESS_NAME}?",
    ])


def _handle_farewell(msg: str) -> str:
    return _rand([
        f"Thanks for stopping by {BUSINESS_NAME}! Have a great day. 👋",
        f"Goodbye! Feel free to come back if you have more questions.",
        f"Take care! We look forward to seeing you at {BUSINESS_NAME}.",
        "Bye! Don't hesitate to reach out if you need anything.",
    ])


def _handle_thanks(msg: str) -> str:
    return _rand([
        "You're very welcome! Is there anything else I can help you with?",
        "Happy to help! Let me know if you have more questions.",
        "Of course! Feel free to ask if you need anything else.",
        "Glad I could help! Anything else you'd like to know?",
    ])


def _handle_hours(msg: str) -> str:
    return _pick("hours", [
        f"We're open {BUSINESS_HOURS}. See you soon!",
        f"Our hours are {BUSINESS_HOURS}. We'd love to see you!",
        f"{BUSINESS_NAME} is open {BUSINESS_HOURS}.",
        f"You can visit us during {BUSINESS_HOURS}.",
    ])


def _handle_location(msg: str) -> str:
    return _pick("location", [
        f"You can find us at {BUSINESS_ADDRESS}.",
        f"We're located at {BUSINESS_ADDRESS}. Hope to see you soon!",
        f"Our address is {BUSINESS_ADDRESS}.",
        f"Come visit us at {BUSINESS_ADDRESS}!",
    ])


def _handle_contact(msg: str) -> str:
    return _pick("contact", [
        f"You can reach us at {BUSINESS_PHONE}. We'd love to hear from you!",
        f"Give us a call at {BUSINESS_PHONE} — we're happy to help.",
        f"The best way to reach us is by phone: {BUSINESS_PHONE}.",
        f"Contact us at {BUSINESS_PHONE} and our team will assist you.",
    ])


def _handle_website(msg: str) -> str:
    return _pick("website", [
        f"You can visit our website at {BUSINESS_WEBSITE} for more information.",
        f"Check us out online at {BUSINESS_WEBSITE}!",
        f"Our website is {BUSINESS_WEBSITE} — feel free to browse.",
        f"Head over to {BUSINESS_WEBSITE} for full details.",
    ])


def _handle_about(msg: str) -> str:
    return _pick("about", [
        f"{BUSINESS_NAME}: {BUSINESS_DESCRIPTION}",
        f"About us — {BUSINESS_DESCRIPTION}",
        f"We're {BUSINESS_NAME}. {BUSINESS_DESCRIPTION}",
    ])


def _handle_pricing(msg: str) -> str:
    return _pick("pricing", [
        f"For pricing details, please call us at {BUSINESS_PHONE} or visit {BUSINESS_WEBSITE}.",
        f"Our team can walk you through pricing — reach us at {BUSINESS_PHONE}.",
        f"For the most accurate pricing, visit {BUSINESS_WEBSITE} or give us a call at {BUSINESS_PHONE}.",
    ])


def _handle_booking(msg: str) -> str:
    return _pick("booking", [
        f"To make a reservation or booking, please call us at {BUSINESS_PHONE}.",
        f"You can book with us by calling {BUSINESS_PHONE}. We'd love to have you!",
        f"For reservations, reach us at {BUSINESS_PHONE} or visit {BUSINESS_WEBSITE}.",
    ])


def _handle_complaint(msg: str) -> str:
    return _pick("complaint", [
        f"We're really sorry to hear that. Your experience matters to us. "
        f"Please call us directly at {BUSINESS_PHONE} so we can make it right.",
        f"That's not the experience we want for you. Please reach out at "
        f"{BUSINESS_PHONE} and we'll take care of it personally.",
        f"We sincerely apologize for the inconvenience. Contact us at "
        f"{BUSINESS_PHONE} — we want to resolve this for you.",
    ])


def _handle_positive_sentiment(msg: str) -> str:
    return _rand([
        f"That's wonderful to hear! We love our customers at {BUSINESS_NAME}. 😊",
        "That makes us so happy to hear! Thank you for the kind words.",
        f"We appreciate that! It's why we love what we do at {BUSINESS_NAME}.",
    ])


def _handle_help(msg: str) -> str:
    return _pick("help", [
        f"I can help you with information about our hours, location, contact details, "
        f"and more. You can also visit {BUSINESS_WEBSITE} or call {BUSINESS_PHONE}.",
        f"Sure! I can answer questions about {BUSINESS_NAME} — try asking about our "
        f"hours, address, or how to contact us.",
        f"Happy to help! You can ask me about our opening hours, location, or "
        f"contact info. For anything else, call us at {BUSINESS_PHONE}.",
    ])


def _handle_urgency(msg: str) -> str:
    return _pick("urgency", [
        f"This sounds urgent — please call us right away at {BUSINESS_PHONE} "
        f"so we can assist you immediately.",
        f"For urgent matters, please reach our team directly at {BUSINESS_PHONE}.",
    ])


def _handle_social(msg: str) -> str:
    return _pick("social", [
        f"For our social media and latest updates, visit {BUSINESS_WEBSITE}.",
        f"Check out {BUSINESS_WEBSITE} to find our social media links and latest news.",
    ])


def _handle_menu_services(msg: str) -> str:
    return _pick("menu_services", [
        f"For our full menu and services, please visit {BUSINESS_WEBSITE} "
        f"or call us at {BUSINESS_PHONE}.",
        f"You can find everything we offer at {BUSINESS_WEBSITE}. "
        f"Feel free to call us at {BUSINESS_PHONE} with any specific questions.",
        f"Our team at {BUSINESS_PHONE} can walk you through everything we have available.",
    ])


def _handle_delivery(msg: str) -> str:
    return _pick("delivery", [
        f"For information about delivery or pickup options, visit {BUSINESS_WEBSITE} "
        f"or call us at {BUSINESS_PHONE}.",
        f"Please call us at {BUSINESS_PHONE} to ask about delivery — we're happy to help!",
    ])


def _handle_confused(msg: str) -> str:
    return _pick("confused", [
        f"Hmm, I want to make sure I help you correctly! You can call us at "
        f"{BUSINESS_PHONE} or visit {BUSINESS_WEBSITE} for more details.",
        f"I'm not entirely sure I understood that. For anything specific, "
        f"our team at {BUSINESS_PHONE} is always ready to help.",
        f"Let me point you to the right place — call us at {BUSINESS_PHONE} "
        f"or browse {BUSINESS_WEBSITE} for detailed information.",
    ])


def _handle_default(msg: str) -> str:
    return _pick("default", [
        f"Thanks for reaching out to {BUSINESS_NAME}! For the best answer, "
        f"please contact us at {BUSINESS_PHONE} or visit {BUSINESS_WEBSITE}.",
        f"I'd love to help! For detailed information, reach our team at "
        f"{BUSINESS_PHONE} or check {BUSINESS_WEBSITE}.",
        f"Great question! Our team can give you the full answer — "
        f"call us at {BUSINESS_PHONE} or visit {BUSINESS_WEBSITE}.",
        f"For anything specific, we recommend reaching out directly at "
        f"{BUSINESS_PHONE}. You can also visit us at {BUSINESS_ADDRESS}.",
    ])


# ---------------------------------------------------------------------------
# Intent registry
# ---------------------------------------------------------------------------
# Order matters: more specific intents must come before general ones.
# Each entry: (key, patterns, keywords, handler)

_INTENTS: list[tuple[str, list[str], list[str], callable]] = [
    # --- Urgency (check before generic help/complaint) ---
    (
        "urgency",
        [r"\burgent\b", r"\bemergency\b", r"\bright now\b", r"\bas soon as possible\b", r"\basap\b"],
        ["urgent", "emergency", "asap", "immediately", "right now"],
        _handle_urgency,
    ),
    # --- Complaints / frustration ---
    (
        "complaint",
        [r"\bthis is (terrible|awful|horrible|bad|unacceptable)\b", r"\bnot (happy|satisfied|pleased)\b",
         r"\bvery (upset|angry|frustrated|disappointed)\b", r"\bworst\b"],
        ["complaint", "complain", "unhappy", "disappointed", "frustrated", "upset",
         "angry", "rude", "terrible", "awful", "horrible", "unacceptable", "refund",
         "disgusting", "never coming back"],
        _handle_complaint,
    ),
    # --- Positive sentiment ---
    (
        "positive",
        [r"\b(love|loved|amazing|excellent|fantastic|wonderful|great|awesome)\b"],
        ["love it", "love this", "amazing", "excellent", "fantastic", "wonderful",
         "great experience", "awesome", "impressed", "so good"],
        _handle_positive_sentiment,
    ),
    # --- Greetings ---
    (
        "greeting",
        [r"^\s*(hi|hello|hey|howdy|hiya|sup|greetings|good\s+(morning|afternoon|evening|day))\b"],
        ["hi", "hello", "hey", "howdy", "hiya", "greetings", "good morning",
         "good afternoon", "good evening", "good day", "what's up", "whats up"],
        _handle_greeting,
    ),
    # --- Farewells ---
    (
        "farewell",
        [r"\b(bye|goodbye|farewell|see\s+you|take\s+care|cya|ttyl|later|good\s*night)\b"],
        ["bye", "goodbye", "farewell", "see you", "take care", "cya", "ttyl",
         "later", "goodnight", "good night", "have a good", "gotta go"],
        _handle_farewell,
    ),
    # --- Thanks ---
    (
        "thanks",
        [r"\b(thank|thanks|thank\s*you|thx|ty|appreciate|grateful)\b"],
        ["thank you", "thanks", "thank you so much", "thx", "ty", "appreciate",
         "grateful", "cheers"],
        _handle_thanks,
    ),
    # --- Hours ---
    (
        "hours",
        [r"\b(open|close|closing|opening|hours?|schedule|timing|when\s+(do\s+you|are\s+you))\b",
         r"\bwhat\s+time\b", r"\bare\s+you\s+open\b"],
        ["hours", "open", "close", "closing", "opening", "schedule", "timing",
         "when do you open", "when do you close", "opening time", "closing time",
         "business hours", "work hours", "operating hours", "what time"],
        _handle_hours,
    ),
    # --- Location / address ---
    (
        "location",
        [r"\b(where|address|location|directions?|find\s+you|get\s+there|near(by)?|map)\b"],
        ["where", "address", "location", "directions", "find you", "get there",
         "how to get", "nearby", "map", "located", "situated", "close to",
         "near me", "navigate"],
        _handle_location,
    ),
    # --- Contact ---
    (
        "contact",
        [r"\b(phone|call|contact|email|reach|get\s+in\s+touch|number|text)\b"],
        ["phone", "call", "contact", "email", "reach", "get in touch",
         "phone number", "telephone", "text", "message", "whatsapp", "reach out"],
        _handle_contact,
    ),
    # --- Website / online ---
    (
        "website",
        [r"\b(website|web\s*site|online|url|link|web\s*page|internet|browse)\b"],
        ["website", "website link", "online", "url", "link", "web page",
         "internet", "browse", "order online", "web address"],
        _handle_website,
    ),
    # --- About / who are you ---
    (
        "about",
        [r"\b(who\s+are\s+you|what\s+(is|are|do)\s+(you|this)|about\s+you|tell\s+me\s+about)\b"],
        ["who are you", "what are you", "what do you do", "about you",
         "tell me about", "what is this", "describe yourself", "your business",
         "what kind of"],
        _handle_about,
    ),
    # --- Pricing / cost ---
    (
        "pricing",
        [r"\b(price|pricing|cost|how\s+much|fee|charge|rate|expensive|cheap|afford)\b"],
        ["price", "pricing", "cost", "how much", "fee", "charge", "rate",
         "expensive", "cheap", "affordable", "budget", "pay", "payment", "quote"],
        _handle_pricing,
    ),
    # --- Booking / reservation ---
    (
        "booking",
        [r"\b(book|reserve|reservation|appointment|schedule\s+a|slot|table)\b"],
        ["book", "reserve", "reservation", "appointment", "schedule a",
         "book a table", "book an appointment", "slot", "availability",
         "available", "make a reservation", "make a booking"],
        _handle_booking,
    ),
    # --- Delivery / pickup ---
    (
        "delivery",
        [r"\b(deliver|delivery|pickup|pick\s*up|takeout|take\s*away|order)\b"],
        ["deliver", "delivery", "pickup", "pick up", "takeout", "take away",
         "take out", "order", "home delivery", "curbside"],
        _handle_delivery,
    ),
    # --- Menu / services ---
    (
        "menu_services",
        [r"\b(menu|service|offer|product|item|special|deal|promotion|what\s+do\s+you\s+(have|sell|serve))\b"],
        ["menu", "services", "offer", "products", "items", "specials", "deals",
         "promotions", "what do you have", "what do you sell", "what do you serve",
         "selection", "options", "variety"],
        _handle_menu_services,
    ),
    # --- Social media ---
    (
        "social",
        [r"\b(instagram|facebook|twitter|tiktok|youtube|social\s*media|follow\s+(you|us))\b"],
        ["instagram", "facebook", "twitter", "tiktok", "youtube", "social media",
         "follow you", "follow us", "@"],
        _handle_social,
    ),
    # --- Help / what can you do ---
    (
        "help",
        [r"\b(help|assist|support|what\s+can\s+you|how\s+can\s+you|what\s+do\s+you\s+know)\b"],
        ["help", "assist", "support", "what can you do", "how can you help",
         "what do you know", "capabilities", "can you", "are you able"],
        _handle_help,
    ),
]


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase and strip extra whitespace."""
    return " ".join(text.lower().split())


def _match_intent(msg: str) -> tuple[str, callable] | tuple[None, None]:
    """
    Check each intent in priority order.
    Returns (key, handler) for the first match, or (None, None).
    """
    normalised = _normalise(msg)

    for key, patterns, keywords, handler in _INTENTS:
        # Regex pattern match
        for pattern in patterns:
            if re.search(pattern, normalised):
                return key, handler
        # Plain keyword match (substring, avoids full tokenisation overhead)
        for kw in keywords:
            if kw in normalised:
                return key, handler

    return None, None


# ---------------------------------------------------------------------------
# Public API — the only function the rest of the app needs
# ---------------------------------------------------------------------------

def get_fallback_response(message: str) -> str:
    """
    Accepts a raw user message string.
    Returns a non-empty response string — guaranteed, never raises.

    Called by the chat endpoint when no API key is configured:
        from backend.fallback import get_fallback_response
        reply = get_fallback_response(request.message)
    """
    if not message or not message.strip():
        return _handle_greeting("")

    try:
        _, handler = _match_intent(message)
        if handler:
            return handler(message)
        # Confused / ambiguous: short message or only punctuation/numbers
        if len(message.strip()) <= 3:
            return _handle_greeting(message)
        return _handle_default(message)
    except Exception:
        # Last-resort safety net — should never be reached
        return (
            f"Thanks for reaching out to {BUSINESS_NAME}! "
            f"Please contact us at {BUSINESS_PHONE} for assistance."
        )