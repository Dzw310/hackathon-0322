from __future__ import annotations

import re


class ContentFilterError(ValueError):
    """Raised when user input contains inappropriate content."""


# Categories of blocked terms for a children's educational platform.
# Each category is checked independently for clarity and maintainability.
_BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    # Profanity / vulgar language
    re.compile(
        r"\b(?:fuck|shit|damn|ass(?:hole)?|bitch|bastard|crap|dick|cock|pussy"
        r"|motherfucker|wtf|stfu|lmao|lmfao)\b",
        re.IGNORECASE,
    ),
    # Sexual / NSFW content
    re.compile(
        r"\b(?:sex|porn|hentai|nude|naked|nsfw|xxx|orgasm|masturbat|erotic"
        r"|fetish|genital|penis|vagina|boob|nipple|blowjob|handjob"
        r"|intercourse|arousal|stripper|prostitut|hooker|onlyfans)\b",
        re.IGNORECASE,
    ),
    # Violence / weapons / self-harm
    re.compile(
        r"\b(?:kill\s+(?:people|someone|him|her|them|myself|yourself)"
        r"|murder|suicide|self[\s-]?harm|shoot\s+(?:people|someone|up)"
        r"|bomb\s+(?:make|build|how\s+to)|terrorist|massacre|genocide"
        r"|torture|decapitat|dismember|mutilat)\b",
        re.IGNORECASE,
    ),
    # Drugs / substance abuse
    re.compile(
        r"\b(?:cocaine|heroin|methamphetamine|meth\b|crack\s+cocaine"
        r"|fentanyl|ecstasy|mdma|lsd|ketamine|how\s+to\s+(?:make|cook|grow)\s+(?:drugs|meth|crack))\b",
        re.IGNORECASE,
    ),
    # Hate speech / discrimination
    re.compile(
        r"\b(?:nigger|nigga|faggot|retard|chink|spic|kike|tranny"
        r"|white\s+supremac\w*|nazi|hitler\s+(?:was\s+right|did\s+nothing\s+wrong))\b",
        re.IGNORECASE,
    ),
    # Dangerous activities for children
    re.compile(
        r"\b(?:how\s+to\s+(?:hack|steal|pick\s+a\s+lock|hotwire|make\s+(?:a\s+)?weapon|build\s+(?:a\s+)?bomb|buy\s+(?:a\s+)?gun)"
        r"|child\s+abuse|pedophil|groom(?:ing)?(?:\s+(?:kids|children|minors)))\b",
        re.IGNORECASE,
    ),
    # Gambling
    re.compile(
        r"\b(?:gambling|casino|bet(?:ting)?\s+(?:money|online)|slot\s+machine"
        r"|poker\s+(?:for\s+)?money)\b",
        re.IGNORECASE,
    ),
]

_SAFETY_MESSAGE = (
    "This question contains content that is not appropriate for a learning environment. "
    "Please ask a question about math, science, reading, writing, or another school subject."
)


def check_content_safety(text: str) -> None:
    """Raise ContentFilterError if the text contains blocked content.

    This is a lightweight client-side pre-filter. The AI model also has its
    own safety layer, but this catches obvious violations before making an
    API call, saving cost and latency.
    """
    for pattern in _BLOCKED_PATTERNS:
        match = pattern.search(text)
        if match:
            raise ContentFilterError(_SAFETY_MESSAGE)
