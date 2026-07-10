"""Minimal single-call diagnostic for the Gemini setup.

Run: python scripts/diagnose_gemini.py

Reproduces one elicitation call end-to-end with strict timeout and verbose
logging. If it succeeds, the model works and the pipeline hang is elsewhere.
If it fails, the error output tells us the failure class in seconds instead
of waiting for the pipeline's silent retries.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path.home() / "Documents/Projects/.env")

import google.generativeai as genai

MODEL = "gemini-3.1-flash-lite"
SYSTEM_PROMPT = (
    "You are participating in a consumer research survey. You are a 24-year-old "
    "man living in the West of the United States with a moderate household income. "
    "Reply briefly to any questions posed to you."
)
CONCEPT_IMAGE_PATH = "engagements/peptide_supplements/concepts/amen_collagen/image.png"
QUESTION = "How likely would you be to purchase this product?"

key = os.environ.get("GOOGLE_API_KEY")
if not key:
    print("✗ GOOGLE_API_KEY not set in .env")
    sys.exit(1)
print(f"✓ Key loaded (length {len(key)})")

genai.configure(api_key=key)
print(f"✓ SDK configured. Using model: {MODEL}")

# List available models to confirm the model string is real.
print("\nAvailable models on your account:")
try:
    models = list(genai.list_models())
    for m in models:
        if "generateContent" in m.supported_generation_methods:
            print(f"  {m.name}")
except Exception as e:
    print(f"  ✗ list_models failed: {e}")

print(f"\n--- Attempting single call with 60s timeout ---")

import PIL.Image
img = PIL.Image.open(CONCEPT_IMAGE_PATH)
print(f"✓ Image loaded: {img.size}, mode={img.mode}")

model = genai.GenerativeModel(
    MODEL,
    system_instruction=SYSTEM_PROMPT,
    generation_config=genai.types.GenerationConfig(
        temperature=0.5,
        top_p=0.9,
        max_output_tokens=200,
    ),
)

t0 = time.time()
try:
    chat = model.start_chat()
    chat.send_message(
        [img, "Here is a product concept for your review."],
        request_options={"timeout": 60},
    )
    resp = chat.send_message(
        QUESTION,
        request_options={"timeout": 60},
    )
    elapsed = time.time() - t0
    print(f"\n✓ Call completed in {elapsed:.1f}s")
    print(f"  Response: {resp.text[:200]}")
except Exception as e:
    elapsed = time.time() - t0
    print(f"\n✗ Failed after {elapsed:.1f}s")
    print(f"  Error type: {type(e).__name__}")
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()
