# Domain Suitability Checklist

Run through this checklist **before** committing to a synthetic survey engagement.
The SSR method's validity depends on the product domain being well-represented
in LLM training data. This checklist helps you assess that risk upfront.

---

## 1. Category Coverage Assessment

**Question:** Is this a consumer product category with abundant online reviews
and discussion?

| Signal | Indicator |
|--------|-----------|
| STRONG | 10,000+ reviews on Amazon/retailer sites for comparable products |
| STRONG | Active subreddit(s) or forum communities discussing the category |
| STRONG | YouTube review/unboxing ecosystem for the category |
| MODERATE | Reviews exist but are sparse (<1,000 for comparable products) |
| WEAK | Primarily B2B; consumers don't publicly discuss this category |
| WEAK | Category is too new to have accumulated meaningful online discussion |

**High-confidence categories (validated or closely analogous to validated):**
Personal care, oral care, skincare, haircare, food & beverage CPG,
household cleaning, consumer electronics accessories, pet products,
OTC health & wellness

**Proceed-with-caution categories:**
Apparel/footwear, home furnishings, toys, mid-range consumer electronics

**Avoid for MVP:**
B2B/industrial, luxury goods, financial products, novel tech with no
existing category, highly regional/cultural niche products

---

## 2. Pre-flight Response Quality Check

Before running a full panel, generate 10-20 free-text responses using varied
personas. Manually inspect them against these criteria:

### Green flags (proceed with confidence)
- [ ] Responses mention **specific, plausible product concerns** (ingredients,
      price, packaging, use-case fit, competitor comparisons)
- [ ] Responses show **variation** — different personas express different levels
      of interest for substantive reasons
- [ ] Responses engage with the **actual concept details**, not just generic
      sentiment
- [ ] Negative responses cite **specific objections** (too expensive, don't need
      it, prefer existing product, skeptical of claims)

### Red flags (reconsider or add heavy caveats)
- [ ] Responses are **generic and vaguely positive** ("This seems like a nice
      product, I might try it") without engaging the concept
- [ ] All personas produce **nearly identical responses** regardless of
      demographics
- [ ] Responses contain **hallucinated features** not present in the concept
- [ ] Responses read like **marketing copy** rather than consumer opinions
- [ ] Negative responses are **vague** ("I'm not sure about this") rather than
      citing specific concerns

---

## 3. Demographic Reliability Check

Based on the paper's findings, assess which demographic breakdowns you can
credibly report:

| Demographic | Paper Finding | Recommendation |
|-------------|---------------|----------------|
| Age | Well-replicated concave pattern | Report with confidence |
| Income | Well-replicated, strong effect | Report with confidence |
| Product category prefs | Well-replicated | Report with confidence |
| Price sensitivity | Well-replicated | Report with confidence |
| Gender | Poorly replicated | Report with caveat or omit |
| Region | Poorly replicated | Report with caveat or omit |
| Ethnicity | Poorly replicated | Report with caveat or omit |

---

## 4. Concept Format Assessment

| Format | Expected Performance |
|--------|---------------------|
| Image with text description + mockup | Best (paper's primary stimulus) |
| Text description only | Slightly lower but viable |
| Image-only (no text) | Not tested — avoid |
| Video/interactive | Not supported |

---

## 5. Sign-off

Before proceeding to a full panel run:

- [ ] Category passes coverage assessment (Section 1)
- [ ] Pre-flight responses show green flags (Section 2)
- [ ] Demographic breakdowns scoped to reliable axes (Section 3)
- [ ] Concept is in a supported format (Section 4)
- [ ] Client has been informed this is synthetic data with stated limitations
- [ ] Reference sets are appropriate for the survey question being asked

**Assessor:** _______________  
**Date:** _______________  
**Client/Project:** _______________  
**Decision:** [ ] PROCEED  [ ] PROCEED WITH CAVEATS  [ ] DO NOT PROCEED
