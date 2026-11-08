"""TTS-ready script preparation.

StoryFlow keeps two versions of every narration block:

* ``Segment.text_content`` — the subtitle / reading version the writer wrote.
* ``Segment.tts_text`` — an optional spoken version produced by the configured
  Script Craft LLM.  It follows strict text-normalisation rules so the voice
  model never improvises laughter, reads "1984" as a number, or stumbles over
  stage directions.

The rules below are deliberately explicit.  They are used both in the LLM
system prompt (for the high-quality rewrite) and in :func:`normalize_tts_text`
as a deterministic safety net for old projects or when no LLM is configured.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Prompt rules
# ---------------------------------------------------------------------------

TTS_SCRIPT_RULES = """You rewrite narration for a text-to-speech engine.
Return ONLY the rewritten narration — no quotes, labels, markdown or commentary.
Preserve the meaning and the sentence order exactly. Do not add or remove facts.

1. STRIP NON-VERBAL ARTEFACTS & EMOTIONAL TAGS
- Remove expressive tags such as [laughs], (chuckles), [sigh], (gasp),
  [giggles] and *laughs*.
- Remove stage and camera directions such as [Music swells],
  (Visual: map zoom) and [Narrator:]. The text must contain spoken words only.
- Remove every emoji and emoticon.

2. NORMALISE NUMBERS AND DATES
- Write calendar years as spoken words:
  1984 -> nineteen eighty-four; 2024 -> twenty twenty-four;
  2005 -> two thousand five.
- Spell out ordinals and dates: July 4th -> July fourth;
  the 21st century -> the twenty-first century.
- Write quantities as spoken words:
  $5.2M -> five point two million dollars; 150kg -> one hundred fifty kilograms;
  40% -> forty percent.
- Write decimals and fractions explicitly:
  3.14 -> three point one four; 1/2 -> one half.

3. EXPAND ACRONYMS AND ABBREVIATIONS
- Letter-by-letter initialisms get hyphens: CIA -> C-I-A, FBI -> F-B-I.
- Keep acronyms that are spoken as words unchanged: NASA, NATO, UNESCO.
- Expand common abbreviations: Dr. -> Doctor, vs. -> versus,
  approx. -> approximately, i.e. -> that is, e.g. -> for example.

4. PUNCTUATION FOR CADENCE
- Replace em dashes, semicolons and slashes with commas or periods.
- Replace trailing ellipses with a comma or period.
- Remove double quotation marks unless a character is literally speaking.
- Keep commas and periods: they are the only reliable breath cues.

5. PHONETIC HINTS
- If a heteronym is ambiguous, rephrase to avoid the collision
  ("He reviewed the letter" instead of "He read the letter").
- For difficult foreign names you may use an intuitive phonetic respelling.
  Never change the spelling in the subtitle script — only in this TTS script.

6. 1:1 ALIGNMENT GUARDRAIL
- Never add explanatory sentences and never omit clauses.
- Keep roughly the same word count so video segment durations stay aligned."""


TTS_REWRITE_SYSTEM_PROMPT = (
    "You are the TTS script editor for StoryFlow. You make narration sound "
    "natural when read by an artificial voice. Follow every rule exactly.\n\n"
    f"{TTS_SCRIPT_RULES}"
)


# ---------------------------------------------------------------------------
# Deterministic cleanup
# ---------------------------------------------------------------------------

_REACTION_WORDS = (
    r"laughs?|laughing|chuckles?|chuckling|sighs?|sighing|giggles?|giggling|"
    r"gasps?|gasping|coughs?|coughing|clears? throat|snorts?|snorting|"
    r"gulps?|whispers?|whispering|shouts?|shouting|scoffs?|scoffing|"
    r"chokes? up|sobs?|sobbing|cries|crying|smiles?|grins?|pauses?"
)

_REACTION_TAG = re.compile(
    rf"[\[(]\s*(?:{_REACTION_WORDS})[^\])\n]*[\])]",
    re.IGNORECASE,
)
_STAGE_DIRECTION = re.compile(
    r"[\[(]\s*(?:music|sfx|sound|audio|visual|visuals|camera|scene|cut to|"
    r"narrator|voiceover|voice over|beat|pause|silence|fade|montage|"
    r"image|shot|b-roll|title card)[^\])\n]*[\])]",
    re.IGNORECASE,
)
_ASTERISK_TAG = re.compile(r"\*[^*\n]{1,60}\*")
_MARKDOWN_EMPHASIS = re.compile(r"(\*{1,3}|_{1,3}|`{1,3})")
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002600-\U000026FF"
    "\U0000FE0F"
    "\U0000200D"
    "]"
)
_DOUBLE_QUOTES = re.compile(r"[\"“”«»„]")
_EM_DASH = re.compile(r"\s*[—–]\s*")
_SEMICOLON = re.compile(r"\s*;\s*")
_SLASH = re.compile(r"\s*/\s*")
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")
_MULTI_SPACE = re.compile(r"[ \t]+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
_REPEATED_PUNCT = re.compile(r"([,.;:!?])(?:\s*[,.;:!?])+")

# Common unit / brand acronyms that are spoken as words rather than spelled.
_SPOKEN_ACRONYMS = {
    "NASA", "NATO", "UNESCO", "UNICEF", "AIDS", "LASER", "RADAR", "SCUBA",
    "SWAT", "GIF", "JPEG", "PNG", "RAM", "ROM", "SQL", "API", "URL", "HTTP",
    "HTTPS", "JSON", "HTML", "CSS", "CPU", "GPU", "USB", "PDF", "DNA", "RNA",
    "BBC", "CNN", "NBC", "ABC", "CBS", "PBS", "NPR",
}

_ABBREVIATIONS = {
    "dr.": "Doctor",
    "mr.": "Mister",
    "mrs.": "Missus",
    "ms.": "Miss",
    "prof.": "Professor",
    "st.": "Saint",
    "vs.": "versus",
    "v.": "versus",
    "approx.": "approximately",
    "i.e.": "that is",
    "e.g.": "for example",
    "etc.": "et cetera",
    "a.m.": "A M",
    "p.m.": "P M",
}

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
    "eighty", "ninety",
]
_SCALES = [
    (1_000_000_000, "billion"),
    (1_000_000, "million"),
    (1_000, "thousand"),
]


def _two_digit_words(number: int) -> str:
    if number < 20:
        return _ONES[number]
    tens, ones = divmod(number, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


def _three_digit_words(number: int) -> str:
    hundreds, rest = divmod(number, 100)
    parts: list[str] = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if rest:
        parts.append(_two_digit_words(rest))
    return " ".join(parts)


def number_to_words(number: int) -> str:
    """Return an integer (0 .. 999,999,999,999) as spoken English words."""
    if number < 0:
        return "minus " + number_to_words(-number)
    if number < 1000:
        return _three_digit_words(number)

    parts: list[str] = []
    remaining = number
    for scale_value, scale_name in _SCALES:
        count, remaining = divmod(remaining, scale_value)
        if count:
            parts.append(f"{number_to_words(count)} {scale_name}")
    if remaining:
        parts.append(_three_digit_words(remaining))
    return " ".join(parts)


def _ordinal_word(token: str) -> str:
    irregular = {
        "one": "first",
        "two": "second",
        "three": "third",
        "five": "fifth",
        "eight": "eighth",
        "nine": "ninth",
        "twelve": "twelfth",
    }
    if token in irregular:
        return irregular[token]
    if "-" in token:
        prefix, _, last = token.rpartition("-")
        return f"{prefix}-{_ordinal_word(last)}"
    if token.endswith("y"):
        return token[:-1] + "ieth"
    if token.endswith("t"):
        return token + "h"
    return token + "th"


def ordinal_to_words(number: int) -> str:
    words = number_to_words(number)
    head, _, last = words.rpartition(" ")
    if not head:
        return _ordinal_word(last)
    return f"{head} {_ordinal_word(last)}"


def year_to_words(year: int) -> str:
    """Read a calendar year naturally (1984, 2005, 2024, ...)."""
    if not 1000 <= year <= 2999:
        return number_to_words(year)

    high, low = divmod(year, 100)
    if high == 20:
        if low < 10:
            return "two thousand" if low == 0 else f"two thousand {_ONES[low]}"
        return f"twenty {_two_digit_words(low)}"
    if high == 19:
        if low == 0:
            return "nineteen hundred"
        if low < 10:
            return f"nineteen oh {_ONES[low]}"
        return f"nineteen {_two_digit_words(low)}"
    if high == 21:
        return "twenty-one" + (f" {_two_digit_words(low)}" if low else "")
    return number_to_words(year)


def _decimal_words(raw: str) -> str:
    whole, _, fraction = raw.partition(".")
    whole_words = number_to_words(int(whole or 0))
    if not fraction:
        return whole_words
    digits = " ".join(_ONES[int(d)] for d in fraction if d.isdigit())
    return f"{whole_words} point {digits}".strip()


def _fraction_to_words(match: re.Match) -> str:
    numerator = int(match.group(1))
    denominator = int(match.group(2))
    if denominator == 0:
        return match.group(0)
    simple = {
        (1, 2): "one half",
        (1, 3): "one third",
        (2, 3): "two thirds",
        (1, 4): "one quarter",
        (3, 4): "three quarters",
    }
    if (numerator, denominator) in simple:
        return simple[(numerator, denominator)]
    denom_words = ordinal_to_words(denominator)
    if numerator != 1:
        denom_words += "s"
    return f"{number_to_words(numerator)} {denom_words}"


def expand_numbers_for_speech(text: str) -> str:
    """Expand years, dates, ordinals, currency, percentages and decimals."""

    # Currency with optional magnitude suffix: $5.2M -> five point two million dollars.
    magnitudes = {
        "k": ("thousand", 1_000),
        "m": ("million", 1_000_000),
        "b": ("billion", 1_000_000_000),
    }

    def currency(match: re.Match) -> str:
        symbol, raw, suffix = match.group(1), match.group(2), match.group(3)
        words = _decimal_words(raw)
        if suffix and suffix.lower() in magnitudes:
            name, _value = magnitudes[suffix.lower()]
            words += f" {name}"
        unit = {"$": "dollars", "£": "pounds", "€": "euros"}.get(symbol, "")
        return f"{words} {unit}".strip()

    text = re.sub(
        r"([$£€])\s*(\d+(?:\.\d+)?)\s*([KkMmBb](?=\b))?",
        currency,
        text,
    )

    def percent(match: re.Match) -> str:
        raw = match.group(1)
        return f"{_decimal_words(raw)} percent"

    text = re.sub(r"\b(\d+(?:\.\d+)?)\s*%", percent, text)

    def fraction(match: re.Match) -> str:
        return _fraction_to_words(match)

    text = re.sub(r"\b(\d+)\s*/\s*(\d+)\b", fraction, text)

    # Compact quantities with unit suffixes: 150kg, 12km, 5ft ...
    units = {
        "kg": "kilograms", "g": "grams", "mg": "milligrams",
        "km": "kilometers", "m": "meters", "cm": "centimeters",
        "mm": "millimeters", "mi": "miles", "ft": "feet",
        "lb": "pounds", "lbs": "pounds", "oz": "ounces",
        "mph": "miles per hour", "kmh": "kilometers per hour",
        "°c": "degrees Celsius", "°f": "degrees Fahrenheit",
    }

    def unit(match: re.Match) -> str:
        value, suffix = match.group(1), match.group(2).lower()
        return f"{_decimal_words(value)} {units.get(suffix, suffix)}"

    text = re.sub(
        r"(?<![\w.])(\d+(?:\.\d+)?)\s*(kg|mg|km|cm|mm|mi|ft|lbs|lb|oz|mph|kmh|°c|°f)\b",
        unit,
        text,
        flags=re.IGNORECASE,
    )
    # Plain metres/grams after the longer suffixes above.
    text = re.sub(
        r"(?<![\w.])(\d+(?:\.\d+)?)\s*(m|g)\b",
        unit,
        text,
        flags=re.IGNORECASE,
    )

    # Ordinals: 21st, 3rd, 4th ...
    def ordinal(match: re.Match) -> str:
        return ordinal_to_words(int(match.group(1)))

    text = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", ordinal, text, flags=re.IGNORECASE)

    # Calendar years (standalone four-digit numbers between 1000 and 2999).
    def year(match: re.Match) -> str:
        return year_to_words(int(match.group(1)))

    text = re.sub(r"(?<![\d.])((?:1\d{3}|2\d{3}))(?![\d]|\.\d)", year, text)

    # Remaining decimals: 3.14 -> three point one four.
    def decimal(match: re.Match) -> str:
        return _decimal_words(match.group(1))

    text = re.sub(r"(?<![\d.])(\d+\.\d+)(?![\d.])", decimal, text)

    # Remaining integers: 150 -> one hundred fifty.
    def integer(match: re.Match) -> str:
        value = int(match.group(1))
        if value > 999_999_999_999:
            return match.group(0)
        return number_to_words(value)

    text = re.sub(r"(?<![\w.])(\d{1,12})(?![\w.])", integer, text)
    return text


def _expand_abbreviations(text: str) -> str:
    def replace(match: re.Match) -> str:
        token = match.group(0).lower()
        return _ABBREVIATIONS.get(token, match.group(0))

    pattern = re.compile(
        r"(?<![\w])(?:" + "|".join(re.escape(key) for key in _ABBREVIATIONS) + r")(?=\s|$)",
        re.IGNORECASE,
    )
    return pattern.sub(replace, text)


def _expand_initialisms(text: str) -> str:
    """Turn letter-by-letter acronyms into ``C-I-A`` style spellings."""

    def replace(match: re.Match) -> str:
        token = match.group(0)
        if token in _SPOKEN_ACRONYMS:
            return token
        # Leave Roman numerals and ordinary words alone.
        if token in {"I", "A"}:
            return token
        return "-".join(token)

    return re.sub(r"\b[A-Z]{2,5}\b", replace, text)


def normalize_tts_text(text: str) -> str:
    """Deterministically clean *text* for a TTS engine.

    This is the safety net used for legacy blocks and as a post-processing step
    after an LLM rewrite.  It is idempotent: running it twice does not change
    the result.
    """
    if not text:
        return ""

    cleaned = unicodedata.normalize("NFKC", str(text))
    cleaned = _REACTION_TAG.sub(" ", cleaned)
    cleaned = _STAGE_DIRECTION.sub(" ", cleaned)
    cleaned = _ASTERISK_TAG.sub(" ", cleaned)
    cleaned = _MARKDOWN_EMPHASIS.sub("", cleaned)
    cleaned = _EMOJI.sub(" ", cleaned)
    cleaned = _DOUBLE_QUOTES.sub("", cleaned)
    cleaned = _expand_abbreviations(cleaned)
    cleaned = expand_numbers_for_speech(cleaned)
    cleaned = _EM_DASH.sub(", ", cleaned)
    cleaned = _SEMICOLON.sub(". ", cleaned)
    cleaned = _SLASH.sub(", ", cleaned)
    cleaned = _ELLIPSIS.sub(", ", cleaned)
    cleaned = _expand_initialisms(cleaned)
    cleaned = _REPEATED_PUNCT.sub(r"\1", cleaned)
    cleaned = _SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"([.!?]){2,}", r"\1", cleaned)
    return cleaned.strip(" ,;:\n\t")


def prepare_tts_text(text: str) -> str:
    """Return the text that should actually be sent to the TTS engine."""
    cleaned = normalize_tts_text(text)
    return cleaned or (text or "").strip()


# ---------------------------------------------------------------------------
# LLM rewrite
# ---------------------------------------------------------------------------


class TTSScriptError(RuntimeError):
    """Raised when the configured model cannot produce a usable TTS script."""


def _extract_rewrite(raw: str) -> str:
    """Pull a plain narration string out of a model reply."""
    if not raw or not raw.strip():
        raise TTSScriptError("The AI model returned an empty TTS script.")

    cleaned = raw.strip()
    # Drop a ```...``` fence if the model added one.
    fence = re.search(r"```(?:text)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()

    # Accept {"tts_text": "..."} even though the prompt asks for plain text.
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            import json

            payload = json.loads(cleaned)
            if isinstance(payload, dict):
                cleaned = str(
                    payload.get("tts_text")
                    or payload.get("text")
                    or payload.get("narration")
                    or ""
                )
        except (ValueError, TypeError):
            pass

    # Strip a single pair of wrapping quotes.
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
        cleaned = cleaned[1:-1]

    cleaned = normalize_tts_text(cleaned)
    if not cleaned:
        raise TTSScriptError("The AI model returned an empty TTS script.")
    return cleaned


def rewrite_for_tts(
    text: str,
    *,
    model: str,
    base_url: str,
    api_key: str = "",
    temperature: float = 0.2,
    timeout: int = 180,
    system_prompt: str = "",
) -> str:
    """Rewrite one narration block into a TTS-ready version using the LLM.

    ``system_prompt`` lets a project supply its own style guide/rules.  The
    built-in :data:`TTS_REWRITE_SYSTEM_PROMPT` is used when it is empty, so
    existing projects keep their current behaviour.  The deterministic
    normalisation and 1:1 length guard still run on every reply.

    Raises :class:`TTSScriptError` on an unusable reply.  Importing the AI
    client lazily keeps this module importable without Django settings.
    """
    source = (text or "").strip()
    if not source:
        raise TTSScriptError("This block has no narration to rewrite.")

    from core_engine import ai_client

    resolved_system_prompt = (
        (system_prompt or "").strip() or TTS_REWRITE_SYSTEM_PROMPT
    )
    messages = [
        {"role": "system", "content": resolved_system_prompt},
        {
            "role": "user",
            "content": (
                "Rewrite this narration block for the TTS voice. "
                "Return only the rewritten spoken text.\n\n"
                f"{source}"
            ),
        },
    ]

    try:
        raw = ai_client.chat_completion(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - re-raise with a useful message
        raise TTSScriptError(str(exc) or "The AI model could not be reached.") from exc

    rewritten = _extract_rewrite(raw)

    source_words = max(len(source.split()), 1)
    rewritten_words = len(rewritten.split())
    # Guard against a model that ignored the 1:1 rule and wrote an essay.
    if rewritten_words > source_words * 3 or rewritten_words < source_words * 0.2:
        raise TTSScriptError(
            "The AI model changed the block too much to keep audio and "
            "subtitles aligned. Try again or edit the TTS script manually."
        )

    return rewritten
