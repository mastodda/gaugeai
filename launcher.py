#!/usr/bin/env python3
"""
launcher.py — Streamlit UI for configuring and launching SSR pipeline runs.

Usage:
    streamlit run launcher.py
"""

import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path.home() / "Documents/Projects/.env")

ROOT = Path(__file__).parent
CONFIG_DIR = ROOT / "config"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="SSR Launcher", page_icon="🧪", layout="wide")
st.title("SSR Launcher")

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

def _init():
    if "stage" not in st.session_state:
        st.session_state.stage = "configure"   # configure | running | done
    if "concept_ids" not in st.session_state:
        st.session_state.concept_ids = [0]     # stable IDs for widget keys
        st.session_state.next_cid = 1
    if "output_dir" not in st.session_state:
        st.session_state.output_dir = None
    if "engagement_path" not in st.session_state:
        st.session_state.engagement_path = None
    if "run_log" not in st.session_state:
        st.session_state.run_log = ""
    if "run_exit_code" not in st.session_state:
        st.session_state.run_exit_code = None

_init()

# ---------------------------------------------------------------------------
# Sidebar — run settings
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Run Settings")

    mode = st.radio(
        "Mode",
        ["full", "paper"],
        help=(
            "**full** — Tier 2 personas + Stage 2 reasoning + insights\n\n"
            "**paper** — Strict Maier et al.: Tier 1 personas, no Stage 2, no insights"
        ),
    )

    st.divider()

    provider = st.selectbox("LLM Provider", ["openai", "google", "anthropic"])
    _model_options = {
        "openai":    ["gpt-4o", "gpt-4o-mini"],
        "google":    ["gemini-3.1-flash-lite", "gemini-3.5-pro"],
        "anthropic": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    }
    model = st.selectbox("Model", _model_options[provider])

    st.divider()

    llm_temp = st.slider(
        "LLM Temperature", 0.0, 1.5, 0.5, 0.1,
        help="Paper used 0.5. Higher = more varied responses.",
    )
    samples = st.selectbox(
        "Samples per Persona", [1, 2, 3], index=1,
        help="Elicitation calls per persona per concept. Paper used 2.",
    )
    seed = st.number_input("Random Seed", value=42, min_value=0)

    if st.session_state.stage != "configure":
        st.divider()
        if st.button("← New Run", use_container_width=True):
            st.session_state.stage = "configure"
            st.session_state.output_dir = None
            st.session_state.run_log = ""
            st.session_state.run_exit_code = None
            st.rerun()

# ---------------------------------------------------------------------------
# CONFIGURE stage
# ---------------------------------------------------------------------------

if st.session_state.stage == "configure":

    # Engagement metadata
    meta_col1, meta_col2 = st.columns(2)
    with meta_col1:
        engagement_name = st.text_input("Engagement Name", "My Concept Test")
    with meta_col2:
        client_name = st.text_input("Client", "")

    st.divider()

    concept_tab, demo_tab = st.tabs(["Concepts", "Demographics"])

    # ── Concepts ─────────────────────────────────────────────────────────────

    with concept_tab:
        to_remove = None

        for cid in list(st.session_state.concept_ids):
            # Derive a display label from whatever name is typed so far
            current_name = st.session_state.get(f"cname_{cid}", "").strip()
            label = current_name or f"Concept {st.session_state.concept_ids.index(cid) + 1}"

            with st.container(border=True):
                hdr, btn = st.columns([8, 1])
                with hdr:
                    st.markdown(f"**{label}**")
                with btn:
                    if len(st.session_state.concept_ids) > 1:
                        if st.button("✕", key=f"crm_{cid}", help="Remove this concept"):
                            to_remove = cid

                st.text_input(
                    "Name", key=f"cname_{cid}",
                    placeholder="e.g. CitrusBurst Sparkling Water",
                )
                st.text_area(
                    "Description", key=f"cdesc_{cid}",
                    height=120,
                    placeholder="Describe the product shown to each persona...",
                )

                img_col, prev_col = st.columns([1, 1])
                with img_col:
                    st.file_uploader(
                        "Concept Image (optional)",
                        type=["png", "jpg", "jpeg"],
                        key=f"cimg_{cid}",
                    )
                with prev_col:
                    uploaded = st.session_state.get(f"cimg_{cid}")
                    if uploaded is not None:
                        uploaded.seek(0)
                        st.image(uploaded.read(), width=220)

        if to_remove is not None:
            st.session_state.concept_ids.remove(to_remove)
            st.rerun()

        if st.button("+ Add Concept"):
            st.session_state.concept_ids.append(st.session_state.next_cid)
            st.session_state.next_cid += 1
            st.rerun()

    # ── Demographics ──────────────────────────────────────────────────────────

    with demo_tab:
        left, right = st.columns(2, gap="large")

        with left:
            panel_size = st.number_input("Panel Size", 10, 500, 100, 10)
            age_min, age_max = st.slider("Age Range", 18, 80, (21, 65))

            st.markdown("**Gender**")
            women_pct = st.slider("Women", 0, 100, 52, format="%d%%")
            men_pct = 100 - women_pct
            st.caption(f"Women {women_pct}%  ·  Men {men_pct}%")

        with right:
            st.markdown("**Region** *(must sum to 100%)*")
            r_midwest   = st.number_input("Midwest",   0, 100, 21, key="r1")
            r_northeast = st.number_input("Northeast", 0, 100, 17, key="r2")
            r_south     = st.number_input("South",     0, 100, 38, key="r3")
            r_west      = st.number_input("West",      0, 100, 24, key="r4")
            region_total = r_midwest + r_northeast + r_south + r_west
            if region_total == 100:
                st.success(f"Total: {region_total}%")
            else:
                st.warning(f"Total: {region_total}% — needs 100%")

            st.markdown("**Income** *(must sum to 100%)*")
            i_low      = st.number_input("Low",            0, 100, 25, key="i1")
            i_moderate = st.number_input("Moderate",       0, 100, 40, key="i2")
            i_upper    = st.number_input("Upper-moderate", 0, 100, 25, key="i3")
            i_high     = st.number_input("High",           0, 100, 10, key="i4")
            income_total = i_low + i_moderate + i_upper + i_high
            if income_total == 100:
                st.success(f"Total: {income_total}%")
            else:
                st.warning(f"Total: {income_total}% — needs 100%")

    st.divider()

    # ── Validation + run button ───────────────────────────────────────────────

    valid_concepts = [
        cid for cid in st.session_state.concept_ids
        if st.session_state.get(f"cname_{cid}", "").strip()
        and st.session_state.get(f"cdesc_{cid}", "").strip()
    ]

    errors = []
    if not valid_concepts:
        errors.append("Add at least one concept with both a name and description.")
    if region_total != 100:
        errors.append(f"Region distribution sums to {region_total}% — must be 100%.")
    if income_total != 100:
        errors.append(f"Income distribution sums to {income_total}% — must be 100%.")

    for err in errors:
        st.error(err)

    if st.button(
        "Run Pipeline",
        disabled=bool(errors),
        use_container_width=True,
        type="primary",
    ) and not errors:

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save uploaded images and build concepts list
        concepts_payload = []
        for idx, cid in enumerate(valid_concepts):
            image_path_str = None
            uploaded = st.session_state.get(f"cimg_{cid}")
            if uploaded is not None:
                images_dir = CONFIG_DIR / "launcher_images" / timestamp
                images_dir.mkdir(parents=True, exist_ok=True)
                img_dest = images_dir / uploaded.name
                uploaded.seek(0)
                img_dest.write_bytes(uploaded.read())
                # Path relative to CONFIG_DIR (where the engagement JSON lives)
                image_path_str = str(img_dest.relative_to(CONFIG_DIR))

            concepts_payload.append({
                "concept_id": f"concept_{chr(ord('a') + idx)}",
                "name": st.session_state[f"cname_{cid}"].strip(),
                "description": st.session_state[f"cdesc_{cid}"].strip(),
                "image_path": image_path_str,
            })

        # Build engagement JSON
        engagement = {
            "_meta": {
                "engagement": engagement_name,
                "client": client_name,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "notes": f"Generated by SSR Launcher. Mode: {mode}.",
            },
            "concepts": concepts_payload,
            "survey_question": {
                "type": "purchase_intent",
                "text": "How likely would you be to purchase this product?",
                "reference_sets_file": "reference_sets.json",
            },
            "demographics": {
                "panel_size": int(panel_size),
                "age_range": [int(age_min), int(age_max)],
                "gender_distribution": {
                    "woman": women_pct / 100,
                    "man": men_pct / 100,
                },
                "region_distribution": {
                    "Midwest":   r_midwest   / 100,
                    "Northeast": r_northeast / 100,
                    "South":     r_south     / 100,
                    "West":      r_west      / 100,
                },
                "income_distribution": {
                    "low":            i_low      / 100,
                    "moderate":       i_moderate / 100,
                    "upper-moderate": i_upper    / 100,
                    "high":           i_high     / 100,
                },
                "ethnicity_distribution": None,
            },
            "pipeline": {
                "mode":                 mode,
                "llm_provider":         provider,
                "llm_model":            model,
                "llm_temperature":      float(llm_temp),
                "llm_top_p":            0.9,
                "reasoning_temperature": 1.0,
                "samples_per_persona":  int(samples),
                "embedding_model":      "text-embedding-3-small",
                "ssr_epsilon":          0.0,
                "ssr_temperature":      1.0,
                "seed":                 int(seed),
            },
        }

        engagement_path = CONFIG_DIR / f"_launcher_{timestamp}.json"
        engagement_path.write_text(json.dumps(engagement, indent=2))

        st.session_state.engagement_path = str(engagement_path)
        st.session_state.output_dir = str(ROOT / "output" / f"run_{timestamp}")
        st.session_state.run_seed = int(seed)
        st.session_state.stage = "running"
        st.rerun()

# ---------------------------------------------------------------------------
# RUNNING stage
# ---------------------------------------------------------------------------

elif st.session_state.stage == "running":
    st.subheader("Pipeline Running")
    st.info("Keep this tab open. Progress updates as each persona is scored.")

    progress = st.empty()

    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "run_pipeline.py"),
            st.session_state.engagement_path,
            "--output", st.session_state.output_dir,
            "--seed",   str(st.session_state.run_seed),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(ROOT),
    )

    log = ""
    for raw in process.stdout:
        # \r is used for in-place progress updates in a terminal; convert for display
        for segment in raw.split("\r"):
            segment = segment.strip()
            if segment:
                log += segment + "\n"
        progress.code(log, language=None)

    process.wait()

    st.session_state.run_log = log
    st.session_state.run_exit_code = process.returncode
    st.session_state.stage = "done"
    st.rerun()

# ---------------------------------------------------------------------------
# DONE stage
# ---------------------------------------------------------------------------

elif st.session_state.stage == "done":
    output_dir = st.session_state.output_dir

    if st.session_state.run_exit_code == 0:
        st.success("Run complete!")
    else:
        st.error(f"Pipeline exited with code {st.session_state.run_exit_code}. Check the log below.")

    st.markdown(f"**Output directory:** `{output_dir}`")

    st.markdown("#### Open in Results Explorer")
    explorer_cmd = f"streamlit run explorer/app.py -- --data-dir {output_dir}"
    st.code(explorer_cmd, language="bash")

    if st.button("Launch Explorer", type="primary"):
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run",
             str(ROOT / "explorer" / "app.py"),
             "--", "--data-dir", output_dir],
            cwd=str(ROOT),
        )
        st.info("Explorer launching — it may take a few seconds to open in your browser.")

    with st.expander("Run Log"):
        st.code(st.session_state.run_log, language=None)

    st.caption(
        f"Engagement config saved to `{st.session_state.engagement_path}` — "
        "keep it to reproduce this run."
    )
