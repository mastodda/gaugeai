# Website Update Plan — Sample Work Section

**Audience:** Claude Code / BMAD agents
**Goal:** Add a "See sample work" section to `websiteonepager.html` that displays slide images from a real engagement deck inline (vertical scroll) plus an ungated download link to the full PPTX. Hosting target: Netlify.

**Hard rule:** Same as prior website plan — no invented stats, no overclaims. The sample is shown as an example of *output format and depth*, not as a case study with claimed business outcomes.

---

## 0. Inputs the user will provide at handoff time

The user will supply, at the start of the task:

1. **Path to the finished sample PPTX deck** — generated specifically for this purpose, dress shirts engagement (uses `example_engagement2.json`).
2. **Confirmation of which slides to feature.** Default behavior if no list is given: feature 6 slides in this order — title slide, executive summary, purchase intent distribution, segment breakdown, qualitative themes, recommended next steps. Agent should present its proposed slide selection to the user for confirmation before building, not after.

If either input is missing at start, the agent should stop and ask — not proceed with placeholders.

---

## 1. Source-of-truth reading order

1. **`/mnt/user-data/outputs/WEBSITE_UPDATE_PLAN.md`** (prior handoff) — confirms the page is mid-update; this section gets added on top of those changes, not before. If those changes haven't shipped yet, this work waits until they do, OR is built on the same branch.
2. **`websiteonepager.html`** — the file being edited.
3. **The provided sample PPTX** — source for the slide images and the download asset.

---

## 2. Asset preparation

### 2.1 Convert PPTX slides to PNG images

The agent should:

1. Use a headless conversion approach (LibreOffice CLI is reliable: `libreoffice --headless --convert-to png <file.pptx>`, or `unoconv`, or render via `python-pptx` + screenshot — pick whichever works in the environment).
2. Export at **1920×1080** native slide resolution. Do not downscale at export time — let the browser handle responsive sizing.
3. Save as PNG (not JPG — text on slides matters; JPG artifacts will be visible).
4. Name files `sample-01.png` through `sample-06.png` (assuming 6 slides; adjust to match the agreed-on selection).

### 2.2 Optimize for web

After export, run each PNG through optimization:

- Target **<300 KB per image**. Most slides will hit this easily; image-heavy slides may need attention.
- Use `pngquant` or `oxipng` for lossless/near-lossless compression. Acceptable to use mozjpeg if a slide is image-dominant and PNG won't compress under target.
- Verify legibility after compression — text must remain crisp at 1x display.

### 2.3 Where assets go

Create directory: `assets/sample/` (or wherever the existing site structure puts assets — check the repo before assuming). Place:

- `sample-01.png` … `sample-06.png`
- `synthpanel-sample-deck.pptx` — the full original PPTX, renamed for the download link

Update `.gitignore` if needed to ensure these are committed (Netlify deploys from the repo).

---

## 3. New section: HTML implementation

Insert a new section between **"How it works"** (currently ends ~line 405 with the `.method-note` block) and **"Why switch"** comparison table (currently starts ~line 408 at `<section class="section-rule reveal">`).

### 3.1 Section structure

```html
<!-- SAMPLE WORK -->
<section class="section-rule reveal">
  <div class="section-label">Sample work</div>
  <h2>What you actually get</h2>
  <p>Below: selected slides from a real engagement testing four dress shirt concepts across 100 synthetic respondents. Same format every client receives.</p>

  <div class="sample-deck">
    <figure class="sample-slide">
      <img src="assets/sample/sample-01.png" alt="Title slide — Dress shirt concept test" loading="lazy">
    </figure>
    <figure class="sample-slide">
      <img src="assets/sample/sample-02.png" alt="Executive summary — Key findings across four concepts" loading="lazy">
    </figure>
    <figure class="sample-slide">
      <img src="assets/sample/sample-03.png" alt="Purchase intent distribution by concept" loading="lazy">
    </figure>
    <figure class="sample-slide">
      <img src="assets/sample/sample-04.png" alt="Segment breakdown — Performance across demographic groups" loading="lazy">
    </figure>
    <figure class="sample-slide">
      <img src="assets/sample/sample-05.png" alt="Qualitative themes — Drivers and barriers" loading="lazy">
    </figure>
    <figure class="sample-slide">
      <img src="assets/sample/sample-06.png" alt="Recommended next steps and methodology summary" loading="lazy">
    </figure>
  </div>

  <div class="sample-download">
    <a href="assets/sample/synthpanel-sample-deck.pptx" download class="cta-button-secondary">Download the full deck (.pptx)</a>
    <p class="sample-download-note">Real output from one engagement. No email gate.</p>
  </div>
</section>
```

### 3.2 Alt text — agent must rewrite to match actual slides

The alt text above is a *placeholder* based on the assumed default slide selection. The agent must update each `alt` attribute to accurately describe the actual slide content of the deck the user provides. Alt text matters for accessibility *and* for prospects browsing on slow connections.

### 3.3 Intro copy — agent must adjust

The intro paragraph (`<p>` after the H2) currently says "100 synthetic respondents" and "four dress shirt concepts." If the actual sample deck differs (e.g., 3 concepts, 150 respondents), update the numbers to match the deck. Don't leave a mismatch between the page copy and what the slides show.

---

## 4. CSS additions

Add to the existing `<style>` block. Keep variable usage consistent with the rest of the site.

```css
/* --- SAMPLE WORK --- */
.sample-deck {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  margin-top: 2.5rem;
  margin-bottom: 2.5rem;
}

.sample-slide {
  margin: 0;
  border: 1px solid var(--rule);
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 2px 12px rgba(26, 26, 26, 0.04);
  transition: box-shadow 0.3s ease, transform 0.3s ease;
}

.sample-slide:hover {
  box-shadow: 0 6px 24px rgba(26, 26, 26, 0.08);
  transform: translateY(-2px);
}

.sample-slide img {
  width: 100%;
  height: auto;
  display: block;
}

.sample-download {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid var(--rule);
  text-align: center;
}

.cta-button-secondary {
  display: inline-block;
  font-family: var(--sans);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ink);
  background: transparent;
  text-decoration: none;
  padding: 0.7rem 1.8rem;
  border: 1.5px solid var(--ink);
  border-radius: 3px;
  transition: all 0.2s;
}

.cta-button-secondary:hover {
  background: var(--ink);
  color: var(--paper);
}

.sample-download-note {
  font-size: 0.82rem;
  color: var(--muted);
  margin-top: 0.8rem;
  font-family: var(--mono);
  letter-spacing: 0.02em;
}

/* Mobile: tighter spacing, no hover lift */
@media (max-width: 720px) {
  .sample-deck { gap: 1.2rem; margin-top: 1.8rem; }
  .sample-slide:hover { transform: none; }
}
```

---

## 5. Performance considerations

Six 1920×1080 PNGs at <300 KB each = ~1.8 MB of image weight on this section. Mitigations:

1. **`loading="lazy"` on all images** — already in the markup above. Ensures images don't load until user scrolls near them.
2. **Optional: serve WebP with PNG fallback.** If the agent wants to be thorough, use a `<picture>` element:

   ```html
   <picture>
     <source srcset="assets/sample/sample-01.webp" type="image/webp">
     <img src="assets/sample/sample-01.png" alt="..." loading="lazy">
   </picture>
   ```

   This typically cuts image weight 25–50%. Agent may skip this if it adds complexity beyond useful gain — the lazy loading is the more important optimization.

3. **Do not add a lightbox/modal viewer.** The slides are sized to be readable at full page width on desktop; on mobile, vertical scroll handles it. Adding a lightbox is scope creep and a maintenance liability.

---

## 6. Netlify-specific notes

- The `assets/sample/` directory will be deployed as part of the static site build. No special config needed if the existing `netlify.toml` (or default build settings) deploys the repo root.
- The PPTX download link is a relative path; Netlify will serve it correctly with the right MIME type by default. If the agent finds `.pptx` files are served as `text/plain`, add to `netlify.toml`:

  ```toml
  [[headers]]
    for = "/*.pptx"
    [headers.values]
      Content-Type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
      Content-Disposition = "attachment"
  ```

- Verify the `download` HTML attribute works as expected — it should force browser download rather than navigation. Test on Chrome and Safari before declaring done.

---

## 7. Copy nuances — what the page should and shouldn't say

The section should be **observational, not boastful**. It's showing, not telling.

| Don't say | Do say |
|---|---|
| "Beautiful, presentation-ready output" | "Same format every client receives" |
| "Insights you can act on immediately" | "Selected slides from a real engagement" |
| "See why brands love SynthPanel" | "What you actually get" |
| Anything implying client testimonial or business outcome from the dress shirt example | Just describe what's shown — it's an internal example, not a case study |

The whole point of inline samples is that the *artifact* does the persuading. Adding marketing puffery around it dilutes that.

---

## 8. Acceptance checklist

Before considering done:

- [ ] Six (or agreed number) slide PNGs exported, optimized to <300 KB each, legible
- [ ] `synthpanel-sample-deck.pptx` available at the download URL, downloads cleanly on Chrome and Safari
- [ ] New section inserted in the correct page position (between "How it works" and "Why switch")
- [ ] Alt text on each `<img>` describes the actual slide content (not the placeholder text in this plan)
- [ ] Intro paragraph numbers match what's actually in the deck (concept count, respondent count)
- [ ] No layout shift on image load (height/aspect ratio preserved via CSS or `width`/`height` attributes)
- [ ] Section renders cleanly on mobile — slides are readable, gap is tight
- [ ] No marketing puffery added — copy stays observational
- [ ] Lighthouse performance score doesn't regress significantly (lazy loading should keep this in check)
- [ ] No console errors, no broken links, no missing assets in the deployed Netlify preview

---

## 9. Out of scope

- Lightbox/modal slide viewer
- Multiple sample decks (one is enough; can add more later if a prospect asks)
- Email-gated download (explicitly ungated per direction)
- Interactive Streamlit embed (separate decision, not part of this work)
- Any analytics/tracking on the download link (can be added later if traffic justifies)
- Editing the deck contents — the deck the user supplies is the deck that ships

If the agent finds itself wanting to expand scope, stop and flag.
