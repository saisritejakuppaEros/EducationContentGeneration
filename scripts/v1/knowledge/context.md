# Explainer-Channel Playbook: Decomposition Formula + Patterns from 9 Creators

**Channels:** Kurzgesagt · MinuteEarth · MinutePhysics · CGP Grey · Life Noggin · Amoeba Sisters · OverSimplified · Simple History · TED-Ed
**Basis:** 768 videos (captions + scene tags + per-video analysis), parsed and measured.

---

## 0. Read this first: what these insights can and cannot tell you

- **No performance data.** The files contain no views, retention, or CTR. Everything below describes *what these channels do*, not proof of *why they win*. Treat the patterns as "what top channels converge on," not as causal laws.
- **Music/audio data is coarse.** Tags only say "background music" / "sound effects" / "none noted". There is no tempo, key, instrumentation, or mix level. "None noted" (e.g. 85% for Kurzgesagt) is an annotation gap, not silence. Audio advice below is about *role and density*, not melody.
- **Trust levels:** High = runtime, turn cadence, sponsor placement, second-person density, visual-mode mix. Medium = scenes/min, hook-type percentages (regex-based). Low / discarded = sentence length and number density (transcript formats differ; MinutePhysics has "000" artifacts).
- **Small samples:** CGP Grey (40 videos) and OverSimplified (32 videos) are thinner; MinuteEarth's ~10 s/scene is likely under-segmented by the scene detector.
- Where a line comes from the dataset's own channel summary rather than my measurements, it's marked *(dataset signature)*.

---

## 1. The Decomposition Formula

```
VIDEO  =  H  +  S  +  E  +  (T × n)  +  P  +  X
          └── spine (storyline) ──────────────┘
OVERLAID WITH:  V (visual grammar)  ·  A (audio grammar)  ·  Vo (voice)  ·  π (pacing)
```

| Layer | Meaning | What to extract when decomposing any video |
|---|---|---|
| **H – Hook** (0–30 s) | The first claim/question/scene that creates a gap | Type (paradox / bold claim / riddle / scene-in-motion / personal anecdote / sponsor-then-gag); word count to first "oddity"; is there a self-correction ("Yes, organ.")? |
| **S – Stakes/Scale** | Why care: cosmic scale, personal relevance, or historical weight | Scale words; is the viewer addressed as "you"? |
| **E – Engine** | The single explanatory mechanism the video runs on | Cascade (A→B→C), tug-of-war (two forces), taxonomy tour, chronology, diagram build, or myth-flip |
| **T – Turns** | Reversals/complications ("but", "however", "yet") | Seconds between turns; where they cluster |
| **P – Payoff** | The answer + its limit | Direct answer? Bounded/hedged? Poetic/ironic button? |
| **X – Exit** | Sponsor, CTA, sign-off ritual, end-screen chain | Position (start / mid / end); segue type; ritual line |
| **V – Visual grammar** | Modes and anchors on screen | % scenes: animation / character / text / map / whiteboard / archival; recurring mascot; cut rate |
| **A – Audio grammar** | Role of sound | Bed (continuous) vs punctuation (SFX) vs voice-only |
| **Vo – Voice** | Grammatical person and register | I / we / you per 1,000 words; humor device; formality |
| **π – Pacing** | Density | Words/min; seconds/scene; runtime |

### Observed parameter ranges (all 9 channels)

| Parameter | Range | Cross-channel typical |
|---|---|---|
| Median runtime | 3.9 – 18.3 min | 4–6 min (shorts), 8–11 min (mid), 18 min (deep serial) |
| Words per minute | 111 – 197 | 135–185 |
| Seconds per scene (median) | 2.3 – 6.6 s (MinuteEarth 10 s, suspect) | 4–6.5 s |
| Reversal ("but/however/yet") every | 33 – 77 s | ≈ 40–60 s |
| "You/your" per 1,000 words | 3.5 – 29.9 | 13–25 |
| Share of all rhetorical questions in first quarter | 30 – 51% | ≈ 35% (uniform would be 25%) |

### Four "engines" the nine channels cluster into (my grouping)

1. **Wonder/scale engine:** Kurzgesagt (+ TED-Ed's story-led pieces)
2. **Puzzle/paradox engine:** MinutePhysics, MinuteEarth, TED-Ed, CGP Grey
3. **Comedy-narrative engine:** OverSimplified (+ CGP Grey's skits)
4. **Host-relationship / teacher engine:** Life Noggin, Amoeba Sisters
5. **Documentary/authority engine:** Simple History

---

## 2. Universal patterns (what most or all of the nine share)

**U1. Open inside the tension, not before it.** First 10–40 words deliver a contradiction, bold claim, riddle, or vivid scene. Kurzgesagt says the alarming sentence and then clarifies it in three words. MinuteEarth states a fact and immediately undercuts it with "But…". TED-Ed poses a physical riddle. Simple History drops into a scene mid-action (a bounty, a worn rifle, a date). *Exception:* OverSimplified and Life Noggin often open with a sponsor read, then reset with a gag or host intro.

**U2. Front-load the questions.** Every channel puts 30–51% of its rhetorical questions in the first quarter (MinuteEarth 51%). Questions open the loop early; the rest of the video closes it.

**U3. Keep a reversal cadence.** A contrast/complication word every ~33–77 s (mean ≈ 53 s). Tightest: MinuteEarth 33 s, CGP Grey 39 s, MinutePhysics 42 s. Loosest: Simple History 77 s (chronology carries momentum instead).

**U4. Make the viewer the protagonist.** "You/your" runs 13–30 per 1,000 words in 7 of 9 channels (Life Noggin 30, Kurzgesagt 25, CGP Grey 20). Everyday-body / everyday-object framing ("your keys", "polarized sunglasses in your drawer"). Only Simple History (3.5) stays detached on purpose.

**U5. Explain with causes, not lists.** "Because / which means / that's why" appears 3.0–3.4 per 1,000 words in CGP Grey, Amoeba Sisters, MinuteEarth, MinutePhysics (the four most "mechanism" channels) vs 0.8–2.0 in the other five (lowest in Simple History and OverSimplified).

**U6. One persistent visual anchor.** A mascot, host, icon-person, stick figure, or whiteboard hand appears in 30–64% of scenes (CGP Grey 64%, MinuteEarth 51%, Life Noggin 49%, Amoeba 44%). Simple History (17%) substitutes archival footage.

**U7. Text on screen is a second narrator.** In the explainers, on-screen text touches 40–89% of scenes (Amoeba 89%, MinuteEarth 86%, Life Noggin 70%, MinutePhysics 67%; percentages exceed 100% when scenes carry multiple modes). Lowest where the image carries the story (Simple History 16%, TED-Ed 24%).

**U8. Sponsors/CTAs are boxed into a labelled block and made feel native.** End-loaded for explainers (Kurzgesagt ≈ 89% through the video, MinuteEarth 88%, MinutePhysics 84%, TED-Ed 98%); front-loaded for OverSimplified (91% of sponsored videos) and Life Noggin (54%). Kurzgesagt bridges the sponsor to the topic metaphor (a "fat" video → "mental metabolism").

**U9. Ritual identity lines.** Repeated sign-on/sign-off phrases: "Hello Internet" (CGP Grey), "Hi, I'm ___" (MinuteEarth), "Keep on thinking" and "Dear Blocko" (Life Noggin), "further reading suggestions" (Amoeba Sisters), "directly funds another moment…" (Kurzgesagt), "Now, where were we?" (OverSimplified).

**U10. Conclude with a bounded answer.** Kurzgesagt ends on "zero evidence" honesty; MinutePhysics: "we haven't proved X impossible, only that any theory would have to…"; MinuteEarth: unlikely events happen given enough time. The payoff is *what's established + what's still open*.

**U11. Anchor abstractions to a concrete, familiar thing.** Telephone game (cell signaling), polarized sunglasses (quantum), potatoes (famine), a raft of driftwood (monkeys). Kurzgesagt has the highest analogy-marker density (≈ 2.0 per 1,000 words, roughly double the rest).

**U12. Title = a curiosity gap in ≤ 7 words (except TED-Ed).** Average 6–8 words (TED-Ed runs ~11 because it credits the expert). Question titles: Life Noggin 65%, MinuteEarth 39%, TED-Ed 48%, Kurzgesagt 19%. Emphasis caps on one word ("SO BAD", "WEIRD", "REALLY"): 17–21% of Life Noggin / MinutePhysics / Amoeba / Simple History titles. OverSimplified: never a question, 81% contain a number (part numbers).

---

## 3. Per-channel playbooks

Format for each: **Identity → Storyline → Infographics/visuals → Music/audio → Voice → Numbers → Signature moves → Steal-this**

### 3.1 Kurzgesagt (99 videos) — *wonder/scale engine*
- **Identity:** Premium flat-vector explainer; existential stakes; big-scale questions about bodies, space, technology, futures.
- **Storyline:** (1) Bold claim that reframes something familiar as strange/dangerous → (2) immediate clarification or myth-flip ("what doesn't kill you makes you stronger" → then dismantle it) → (3) scale/context → (4) mechanism as a **cascade** (e.g., fat cells outgrow blood supply → stress → brain stops hearing the fullness signal → hormones drift → downstream symptoms) or a **two-titans fight** (dark energy vs gravity) → (5) implications/scenarios → (6) honest uncertainty, sometimes a poetic close → (7) soft support ask/sponsor.
- **Infographics/visuals:** 2D vector animation in ~55% of scenes; characters ~36%; on-screen text ~42%; maps/diagrams ~10%. Recurring bird mascot, saturated palette, metaphor-first frames *(dataset signature)*. Forces and organs are personified.
- **Music/audio:** Continuous orchestral/ambient bed *(dataset signature)*; tagged music ≈ 24% and SFX ≈ 23% of scenes with "none noted" ≈ 85% (annotation gap). SFX are sparse and diegetic (a sharp pain sound, buzzing flies) used as punctuation over the bed.
- **Voice:** Institutional "we" (≈ 21/1k) with almost no "I" (0.5/1k) + heavy "you" (25/1k): a collective lab speaking to *your* body/future. Highest analogy density.
- **Numbers:** 11.4 min median; 142 wpm; 6.4 scenes/min (~6.6 s/scene); reversal every ~49 s; sponsor/support ask in ~55% of videos, ~89% through.
- **Signature moves:** Anthropomorphic framing; sponsor segue that reuses the topic metaphor; a "support this channel" ritual that ties purchases to future videos.
- **Steal-this:** State the scariest-true sentence first, then define terms. Explain any system as a cascade with rising stakes. End with what is *not* known.

### 3.2 MinuteEarth (99 videos) — *puzzle engine, fastest turns*
- **Identity:** Fast Earth/life science; rotating hosts; stick-figure and map visuals.
- **Storyline:** Surprising fact → **"but" contradiction** → host intro ("Hi, I'm ___") → the absurd hypothesis stated plainly → **stack of reasons it seems impossible** ("first… fourth… fifth…") → the **rescue** (features that make it slightly likelier) → a real documented instance (e.g., a natural raft carrying iguanas across the sea) → closing line about deep time or scale → sponsor/poster/credits.
- **Infographics/visuals:** Hand-drawn maps and diagrams; on-screen text in ~86% of scenes; 2D animation ~65%; characters ~51%; maps ~24%; minimal/static frames ~15%.
- **Music/audio:** SFX-led (≈ 62% of scenes) with short music stings; clean VO blocks.
- **Voice:** Conversational "we/I" (≈ 12/1k "we"), lower "you" (9/1k) than peers; connective phrases "That's because…", "Here's where…", "scientists call…". Dry jokes (a "doggone gorgeous poster").
- **Numbers:** 3.9 min median; 184 wpm (second fastest); reversal every ~33 s (tightest of all); 51% of questions in the first quarter; sponsor in ~53% of videos, ~88% through; 30% of hooks use extreme/contrarian language; 39% question titles.
- **Steal-this:** Make the claim *sound ridiculous*, prove why it's ridiculous, then earn the rescue with evidence. Keep videos to 4 minutes; reverse every ~30 s.

### 3.3 MinutePhysics (100 videos) — *diagram-first paradox engine*
- **Identity:** Whiteboard/minimal intuition-building for physics.
- **Storyline:** Everyday object the viewer owns → reveal it's a measurement device → **paradox** → diagrams built step by step (Venn circles, filters) with concrete percentages → close the loop on exactly what was and wasn't proved. Frequent **frame-shift** move: "from the perspective of the moving object…".
- **Infographics/visuals:** Highest diagram-first mix: whiteboard ~23%, minimal/static ~24%, maps/diagrams ~26%, on-screen text ~67%. Fastest cutting (≈ 2.3 s median scene; ~14 scenes/min).
- **Music/audio:** SFX ≈ 53%, background music ≈ 22% (used on longer beats); transitions carry sound.
- **Voice:** Neutral instructor; "you" 19/1k; precise hedging.
- **Numbers:** 4.9 min median; 197 wpm (fastest); reversal every ~42 s; Brilliant-style sponsor in ~65% of videos, ~84% through.
- **Steal-this:** One diagram, built incrementally; every step changes one thing. Finish with a *carefully bounded* claim, not a flourish.

### 3.4 CGP Grey (40 videos) — *systems claim engine, personal voice*
- **Identity:** Info-dense explainers on politics, cities, and systems; flexible into vlog/tier-list formats.
- **Storyline:** Provocative claim ("use the system to subvert the system") → definitions and reset of assumptions ("remember that…") → **planted notes** ("let's make a note of that") that pay off later → system model → consequences → **comic time-travel skit** or dry button.
- **Infographics/visuals:** Icon-people + maps/flags/diagrams; characters ≈ 64% of scenes; text ≈ 40%; rapid cuts (≈ 10 scenes/min, ~4 s), minimal decoration.
- **Music/audio:** Voice carries. Audio tagged "none" in ~93% of scenes; SFX ≈ 3%. Silence and voice as the main instrument.
- **Voice:** Most personal narrator: "I" ≈ 24/1k (every other channel is ≤ 13); pedantic-comedic asides; tangent deferral ("story for another time").
- **Numbers:** 6.6 min median; 136 wpm; reversal every ~39 s; sponsor rare (~8%).
- **Steal-this:** Plant-and-payoff: set a "note" early, cash it in at the end. Use voice + pacing rather than music for tension.

### 3.5 Life Noggin (100 videos) — *host-relationship engine*
- **Identity:** Pop-science listicle/Q&A with a block-character host (Blocko).
- **Storyline:** Title question (often pop-culture or emotional) → **sponsor first** (in ~54% of sponsored videos) → host intro → a "Dear Blocko" viewer question or scenario ("you misplace your keys…") → **fact stack** with relatable jokes → opinion/advice → end-screen chaining and "Keep on thinking".
- **Infographics/visuals:** 3D/block character host; bold text hooks; bright studio look *(dataset signature)*; text ≈ 70% of scenes; branding/title cards ≈ 13% (highest); characters ≈ 49%.
- **Music/audio:** SFX ≈ 58%, music ≈ 12%; a brand sting placed after the premise ("cue the intro").
- **Voice:** Most direct second-person channel (≈ 30 "you"/1k) and most question marks (8.4/1k); self-deprecating jokes.
- **Numbers:** 4.0 min median; 176 wpm; reversal every ~47 s; 65% of titles are questions; 40% of hooks are questions.
- **Steal-this:** Turn every topic into "a question a viewer typed to you." Reuse a fixed format ("Dear ___") so each video is a slot to fill.

### 3.6 Amoeba Sisters (100 videos) — *teacher engine*
- **Identity:** Classroom biology with sister mascots; learning-objective driven.
- **Storyline:** **Personal anecdote or shared memory** ("when I was a kid…", "in ninth grade…") → learning goal → concept diagram → **recall check** ("you remember transcription, right?") → example (often animal-model study) → **signposting** ("two quick points before I move on") → recap → "further reading suggestions" list.
- **Infographics/visuals:** Bright cartoon cells/organisms; textbook-style diagrams; **on-screen key terms in ~89% of scenes** (highest); 2D animation ≈ 70%; sisters as characters ≈ 44%.
- **Music/audio:** SFX ≈ 52% for emphasis and jokes; study-music segments in some catalog items *(dataset signature)*.
- **Voice:** Inclusive "we/our" (≈ 23/1k, highest of all) + "you" 16/1k; warm, curious.
- **Numbers:** 8.3 min median; 164 wpm; reversal every ~56 s; sponsor rare (≈ 6%); "further reading" ritual in ~28 videos.
- **Steal-this:** Start with the human reason you care, tie each new term to a prior term ("remember…"), and end with a self-study path.

### 3.7 OverSimplified (32 videos) — *comedy-narrative engine*
- **Identity:** Long-form comedic history documentaries; serialized in parts; "MiniWars" shorts.
- **Storyline:** Sponsor read (91% of sponsored videos start with it) → **cold-open gag or quiz** ("you have two seconds to name these countries…") → chaptered timeline with dates and maps → **modern-slang dialogue** between historical figures ("Hey man…") → direct mock-advice to the viewer → ironic aftermath/punchline exit ("Except for this guy.").
- **Infographics/visuals:** Flat character animation + maps (maps ≈ 26% of scenes); frequent cuts (~4 s); all-caps shouting for emphasis in the transcript; text ≈ 46%; live/archival ≈ 10%.
- **Music/audio:** **Most SFX-driven (≈ 79% of scenes)**: comedic hits timed to the punchline; music reserved for set-pieces (≈ 10%).
- **Voice:** Deadpan narrator + anachronistic character voices; "you" appears heavily but much of it is the sponsor read. Callback: "Now, where were we?" resumes the story after the ad.
- **Numbers:** **18.3 min median** (longest); 116 wpm (slowest, since gags need pauses); reversal every ~69 s; sponsors in ~82% of videos, merch inside the read (character pins).
- **Steal-this:** Give each historical figure one comedic personality trait, keep the real facts accurate, let SFX land the joke, and use "where were we?" to re-enter after any ad.

### 3.8 Simple History (99 videos) — *documentary/authority engine*
- **Identity:** Military and history; archival footage mixed with animation and maps.
- **Storyline:** In-medias-res hook (an extreme fact, a worn object, a date under pressure, or a "why would…?" question) → **chronology or taxonomy** (e.g., tactical vs emergency vs retention reloads) → battle/map → outcome → epilogue linking to **pop-culture legacy** (a film, a game).
- **Infographics/visuals:** Highest live/archival share (≈ 15%) plus animation (≈ 44%); on-screen text lowest (≈ 16%): the *image* is the evidence; few maps (~6%).
- **Music/audio:** SFX ≈ 62% (gunfire, engines, ambience) with dramatic background music *(dataset signature)*; ≈ 6% tagged music.
- **Voice:** Detached documentary narrator: "you" 3.5/1k, "I" 0.5/1k, fewest questions (0.9/1k); dates and figures spelled out in word form.
- **Numbers:** 9.9 min median; 133 wpm; slowest reversal cadence (~77 s); sponsor in ~27% of videos.
- **Steal-this:** Use authoritative flatness plus a startling first fact. Let ambient sound design sell the setting, and close by tying the past to something the viewer already knows.

### 3.9 TED-Ed (99 videos) — *literary lesson engine*
- **Identity:** Short expert-scripted lessons with painterly 2D animation; titles credit the expert.
- **Storyline:** **Riddle/dilemma or hypothetical** ("how can a bigger tube fit inside a smaller one?", "if you could be immortal…") → context → mechanism → gallery of variations (many snake species, many diets) → final twist/oddity → moral or takeaway. Some are allegorical stories (a wizard-world analogy for knowledge access).
- **Infographics/visuals:** Stylized 2D animation ≈ 51%; characters ≈ 38%; least text on screen (≈ 24%): the illustration does the teaching.
- **Music/audio:** **Most music-forward (≈ 27% tagged bg music)**; narration is the anchor. SFX ≈ 23%.
- **Voice:** Measured, literary; "you" 13/1k; sponsors almost absent (≈ 4%) and always at the very end.
- **Numbers:** 5.8 min median; 111 wpm (partly a transcript-coverage effect); reversal every ~68 s; titles: 48% questions, longest (≈ 10.7 words), expert credited.
- **Steal-this:** Frame the lesson as a puzzle a curious person would ask; teach with one central image; end on a twist that reframes the puzzle.

---

## 4. Cross-channel comparison

| Channel | Videos | Median runtime (min) | Words/min | Sec/scene | Reversal every | "You"/1k | SFX % scenes | Bg-music % scenes | Sponsor: presence · position |
|---|---|---|---|---|---|---|---|---|---|
| Kurzgesagt | 99 | 11.4 | 142 | 6.6 | 49 s | 25 | 23* | 24* | 55% · end (~89%) |
| MinuteEarth | 99 | 3.9 | 184 | 10.2† | 33 s | 9 | 62 | 12 | 53% · end (~88%) |
| MinutePhysics | 100 | 4.9 | 197 | 2.3 | 42 s | 19 | 53 | 22 | 65% · end (~84%) |
| CGP Grey | 40 | 6.6 | 136 | 4.1 | 39 s | 20 | 3 | 6 | 8% · mixed |
| Life Noggin | 100 | 4.0 | 176 | 6.4 | 47 s | 30 | 58 | 12 | 34% · start (54%) |
| Amoeba Sisters | 100 | 8.3 | 164 | 6.5 | 56 s | 17 | 52 | 19 | 6% · early/mid |
| OverSimplified | 32 | 18.3 | 116 | 4.0 | 69 s | 17‡ | 79 | 10 | 82% · start (91%) |
| Simple History | 99 | 9.9 | 133 | 5.3 | 77 s | 3.5 | 62 | 6 | 27% · mid/end |
| TED-Ed | 99 | 5.8 | 111 | 5.7 | 68 s | 13 | 23* | 27 | 4% · end (98%) |

\* Under-annotated (dominant "none noted"); real music use is higher. † Likely under-segmented. ‡ Inflated by sponsor reads.

---

## 5. Blend recipes (which channel to borrow from for which goal)

| If the goal is… | Borrow from | Core moves |
|---|---|---|
| Emotional weight / big stakes | Kurzgesagt + TED-Ed | Bold claim, cascade, music bed, honest uncertainty |
| Fast curiosity in ≤ 4 min | MinuteEarth + MinutePhysics | Paradox open, reversal every 30–40 s, text-heavy frames |
| Comedy with real facts | OverSimplified + CGP Grey | Anachronistic dialogue, SFX-timed jokes, plant-and-payoff |
| Friendly teaching / retention | Amoeba Sisters + Life Noggin | Anecdote hook, recall checks, recurring host, end-screen chain |
| Gravitas / authenticity | Simple History | In-medias-res, archival evidence, ambient SFX, detached voice |
| Monetization without breaking flow | Kurzgesagt (end, topic-bridged) or OverSimplified (front-loaded with a joke) | Pick one placement and make it in-voice |

---

## 6. Paste-ready instruction block for your AI model

```
You are writing/directing an educational explainer video. Apply these patterns
distilled from nine top explainer channels.

STORYLINE
- Hook (first 10–40 words): open on a contradiction, a bold-then-clarified claim,
  a riddle, or a scene already in motion. No preamble. Ask the central question
  early; place ~1/3 of all rhetorical questions in the first quarter.
- Stakes: tie the topic to the viewer's own body, objects, or future ("you/your"),
  at ~15–25 uses per 1,000 words (skip for a documentary tone).
- Engine: pick ONE — cascade (A→B→C with rising stakes), two forces in a tug-of-war,
  myth-flip, taxonomy tour, chronology, or step-by-step diagram build.
- Turns: introduce a complication/reversal ("but / however / yet") about every
  40–60 seconds (as fast as every 30 s for shorts; up to ~75 s for chronology).
- Explain with causes: use "because / which means / that's why" rather than lists.
- Plant a note early ("remember this") and pay it off near the end.
- Payoff: give the answer AND its limit ("what we know / what we don't").
- Exit: one ritual sign-off line; end-screen chain to a related video.

VISUALS / INFOGRAPHICS
- One persistent anchor (mascot, host, icon-people, stick figure, or whiteboard hand).
- Concept diagrams built incrementally; one change per step; concrete numbers.
- On-screen text for key terms in 40–90% of scenes (explainers); minimal text when
  the image itself is the evidence (history/documentary).
- Scene length 4–6.5 s typical; 2–3 s for diagram-driven physics; 4 s for comedy.
- Metaphor-first frames for abstract ideas; personify forces (dark energy vs gravity).
- Maps for anything with geography; archival footage when authenticity matters.

AUDIO
- Choose ONE role: (a) continuous ambient/orchestral BED for emotion and scale,
  (b) SFX as PUNCTUATION for jokes/emphasis (highest for comedy, ~60–80% of scenes),
  (c) VOICE-ONLY with almost no music for dense argument.
- Duck or remove music during the densest explanation; bring it up on reveals.
- Add diegetic ambience for history (engines, gunfire); keep it under the voice.

VOICE
- Pick a person and stay there: collective "we" (institutional), "I" (personal essay),
  "you" (host-to-viewer), or detached narrator (documentary).
- Use concrete analogies tied to everyday objects. Add one dry aside per minute
  at most; never let the joke replace the mechanism.

PACING / FORMAT
- 4 min for single-idea shorts, 6–10 min for mid-depth, 10–18 min for deep dives.
- Words per minute: 135–185 (up to ~195 for intense diagram videos; ~115 for comedy).
- Sponsor: a labelled block, either at the START with a joke or at the END with a
  segue that reuses the video's metaphor. Never mid-mechanism.

TITLE
- ≤ 7 words. Curiosity gap or "Why/How/What/Could" question, with at most ONE
  emphasised word in caps.
```

### Decompose-a-video prompt (to run on any new reference video)

```
Given this transcript + scene list, output JSON:
{
  "hook": {"type": "...", "words_to_first_oddity": 0, "self_correction": true/false},
  "stakes": {"scale_or_personal": "...", "you_per_1k_words": 0},
  "engine": "cascade | two-forces | myth-flip | taxonomy | chronology | diagram-build",
  "turns": {"count": 0, "avg_seconds_between": 0, "positions": [ ... ]},
  "payoff": {"answer": "...", "stated_limit": "..."},
  "exit": {"sponsor_position_pct": 0, "segue_type": "...", "ritual_line": "..."},
  "visual": {"anchor": "...", "mode_mix_pct": {...}, "avg_sec_per_scene": 0},
  "audio": {"role": "bed | punctuation | voice-only", "notes": "..."},
  "voice": {"person": "I|we|you|detached", "humor_device": "..."},
  "pacing": {"wpm": 0, "runtime_min": 0}
}
Then list the 3 moves that make this video distinct from a generic explainer.
```