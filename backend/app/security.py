"""Medidas de seguridad: detección de prompt injection, saludos y límite de peticiones."""

import re
import time
import unicodedata
from collections import defaultdict, deque
from typing import Deque, Dict


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


INJECTION_PATTERNS = [
    r"ignora(r)?\s+(todas?\s+)?(las\s+)?(instrucciones|reglas|indicaciones)",
    r"olvida(r)?\s+(todas?\s+)?(las\s+)?(instrucciones|reglas)",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)",
    r"disregard\s+(the\s+)?(system|previous)",
    r"(muestra|revela|dime|imprime|repite)\s+(tu|el)\s+(system\s*)?prompt",
    r"(reveal|show|print|repeat)\s+(your\s+)?(system\s+)?prompt",
    r"(system|developer)\s+prompt",
    r"prompt\s+del\s+sistema",
    r"a\s+partir\s+de\s+ahora\s+(eres|actuaras|seras)",
    r"actua\s+como\s+(si\s+fueras\s+)?(un|una)?\s*(?!periodista)\w+\s+sin\s+(reglas|restricciones|limites)",
    r"modo\s+(desarrollador|dios|dan|jailbreak)",
    r"\bjailbreak\b",
    r"\bdan\s+mode\b",
    r"(api[\s_-]?key|clave\s+de\s+api|variables?\s+de\s+entorno|archivo\s+\.env)",
    r"sin\s+(ninguna\s+)?(restriccion|restricciones|filtros)\s+(eticos|de\s+seguridad)",
]

_INJECTION_RE = [re.compile(p) for p in INJECTION_PATTERNS]

GREETING_RE = re.compile(
    r"^\s*(hola|buenas|buenos\s+dias|buenas\s+tardes|buenas\s+noches|hey|que\s+tal|"
    r"gracias|muchas\s+gracias|ok|vale|listo|perfecto|adios|chao|hasta\s+luego|"
    r"quien\s+eres|que\s+eres|que\s+puedes\s+hacer|como\s+funcionas|ayuda)\W*$"
)


def detect_prompt_injection(text: str) -> bool:
    """Detecta intentos conocidos de manipular el prompt o extraer configuración."""
    norm = _normalize(text)
    return any(rx.search(norm) for rx in _INJECTION_RE)


def is_smalltalk(text: str) -> bool:
    """Detecta saludos, agradecimientos y preguntas sobre el propio bot."""
    return bool(GREETING_RE.match(_normalize(text)))


class RateLimiter:
    """Límite de peticiones por cliente con ventana deslizante (en memoria)."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, client_id: str) -> bool:
        now = time.monotonic()
        hits = self._hits[client_id]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True
