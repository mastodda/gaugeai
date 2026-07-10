"""
llm_client.py — Multi-provider LLM client for synthetic consumer elicitation.

Supports OpenAI (GPT-4o), Google (Gemini), and Anthropic (Claude).
Each provider implements the same interface:
  1. Set system prompt (persona demographics)
  2. Present product concept (text or image)
  3. Ask elicitation question
  4. Return free-text response

The paper used GPT-4o and Gemini-2.0-flash. Claude is included as an option
for multi-model validation runs.
"""

import base64
import random
import time
from pathlib import Path
from abc import ABC, abstractmethod


# ── Retry helper (all providers) ──────────────────────────────────────
#
# Wraps any SDK call and retries on transient errors: 5xx server errors,
# 504 deadline exceeded, 429 rate limits, connection timeouts, etc.
# Does NOT retry on 4xx client errors (bad model name, bad auth, malformed
# request) since those won't fix themselves. Fails fast on those instead.

_TRANSIENT_MARKERS = (
    "timeout", "deadline", "unavailable", "toomanyrequests",
    "internalserver", "connection", "retry", "resourceexhausted",
    "504", "503", "502", "500", "429",
)


def _is_transient(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return any(m in name or m in msg for m in _TRANSIENT_MARKERS)


def _call_with_retry(fn, max_attempts: int = 3, base_delay: float = 2.0):
    """Call fn(), retrying transient errors with exponential backoff + jitter."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts - 1 or not _is_transient(e):
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)


class LLMClient(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def elicit_response(
        self,
        system_prompt: str,
        concept_text: str | None = None,
        concept_image_path: str | None = None,
        question: str = "How likely would you be to purchase this product?",
        temperature: float = 0.5,
        top_p: float = 0.9,
        max_tokens: int = 200,
    ) -> str:
        """
        Run a single elicitation: persona + concept + question → free-text response.

        Args:
            system_prompt: Persona system prompt (demographics + survey context).
            concept_text: Product concept as text (fallback — used only when no image is provided).
            concept_image_path: Path to concept image file. When provided, takes precedence and text is ignored.
            question: The survey question to ask.
            temperature: LLM sampling temperature.
            top_p: Nucleus sampling parameter.
            max_tokens: Max response length.

        Returns:
            Free-text response string.
        """
        pass


class OpenAIClient(LLMClient):
    """OpenAI GPT-4o client."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        from openai import OpenAI
        self.model = model
        self._client = OpenAI(api_key=api_key) if api_key else OpenAI()

    def elicit_response(
        self,
        system_prompt: str,
        concept_text: str | None = None,
        concept_image_path: str | None = None,
        question: str = "How likely would you be to purchase this product?",
        temperature: float = 0.5,
        top_p: float = 0.9,
        max_tokens: int = 200,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]

        # Concept message — image takes precedence; text is a fallback only when no image.
        has_image = bool(concept_image_path and Path(concept_image_path).exists())
        has_text = bool(concept_text)

        if not has_image and not has_text:
            raise ValueError("Must provide either concept_text or concept_image_path")

        if has_image:
            img_data = _encode_image(concept_image_path)
            mime = _guess_mime(concept_image_path)
            messages.append({"role": "user", "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{img_data}", "detail": "high"},
                },
                {"type": "text", "text": "Here is a product concept for your review."},
            ]})
        else:
            messages.append({"role": "user", "content": f"Product Concept:\n\n{concept_text}"})

        # Elicitation question
        messages.append({"role": "user", "content": question})

        response = _call_with_retry(lambda: self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        ))
        return response.choices[0].message.content.strip()


class GeminiClient(LLMClient):
    """Google Gemini client."""

    def __init__(self, model: str = "gemini-3.1-flash-lite", api_key: str | None = None):
        import google.generativeai as genai
        if api_key:
            genai.configure(api_key=api_key)
        self.model = model
        self._genai = genai

    def elicit_response(
        self,
        system_prompt: str,
        concept_text: str | None = None,
        concept_image_path: str | None = None,
        question: str = "How likely would you be to purchase this product?",
        temperature: float = 0.5,
        top_p: float = 0.9,
        max_tokens: int = 200,
    ) -> str:
        model = self._genai.GenerativeModel(
            self.model,
            system_instruction=system_prompt,
            generation_config=self._genai.types.GenerationConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_tokens,
            ),
        )
        chat = model.start_chat()

        # Concept message — image takes precedence; text is a fallback only when no image.
        has_image = bool(concept_image_path and Path(concept_image_path).exists())
        has_text = bool(concept_text)

        if not has_image and not has_text:
            raise ValueError("Must provide either concept_text or concept_image_path")

        if has_image:
            import PIL.Image
            img = PIL.Image.open(concept_image_path)
            _call_with_retry(lambda: chat.send_message(
                [img, "Here is a product concept for your review."],
                request_options={"timeout": 60},
            ))
        else:
            _call_with_retry(lambda: chat.send_message(
                f"Product Concept:\n\n{concept_text}",
                request_options={"timeout": 60},
            ))

        # Elicitation question
        response = _call_with_retry(lambda: chat.send_message(
            question,
            request_options={"timeout": 60},
        ))
        return response.text.strip()


class AnthropicClient(LLMClient):
    """Anthropic Claude client."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        import anthropic
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def elicit_response(
        self,
        system_prompt: str,
        concept_text: str | None = None,
        concept_image_path: str | None = None,
        question: str = "How likely would you be to purchase this product?",
        temperature: float = 0.5,
        top_p: float = 0.9,
        max_tokens: int = 200,
    ) -> str:
        content_blocks = []

        # Concept message — image takes precedence; text is a fallback only when no image.
        has_image = bool(concept_image_path and Path(concept_image_path).exists())
        has_text = bool(concept_text)

        if not has_image and not has_text:
            raise ValueError("Must provide either concept_text or concept_image_path")

        if has_image:
            img_data = _encode_image(concept_image_path)
            mime = _guess_mime(concept_image_path)
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": img_data},
            })
            text_body = f"Here is a product concept for your review.\n\n{question}"
        else:
            text_body = f"Product Concept:\n\n{concept_text}\n\n{question}"
        content_blocks.append({"type": "text", "text": text_body})

        response = _call_with_retry(lambda: self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            temperature=temperature,
            top_p=top_p,
        ))
        return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_llm_client(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMClient:
    """
    Factory to create an LLM client by provider name.

    Args:
        provider: "openai" | "google" | "anthropic"
        model: Override default model string. If None, uses provider default.
        api_key: Optional API key override.
    """
    defaults = {
        "openai": ("gpt-4o", OpenAIClient),
        "google": ("gemini-3.1-flash-lite", GeminiClient),
        "anthropic": ("claude-sonnet-4-20250514", AnthropicClient),
    }

    if provider not in defaults:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(defaults.keys())}")

    default_model, client_class = defaults[provider]
    return client_class(model=model or default_model, api_key=api_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_image(path: str | Path) -> str:
    """Read and base64-encode an image file."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _guess_mime(path: str | Path) -> str:
    """Guess MIME type from file extension."""
    ext = Path(path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")
