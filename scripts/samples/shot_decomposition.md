"The Signal" — 20-Minute Storyboard
Format legend
🎬 WAN = generic cinematic video AI (WAN 2.2-class) — story, dialogue, character beats, ship/space visuals. Max 2:00 per clip (we stay ≤1:00 everywhere for pacing).
📐 Manim = math-generation module — equation on screen, minimal motion, high-level concept only. No decoration, no long derivations.
Cast: M = Mathematician (poses the real-world problem), F = Friend (teaches, smarter, guides), Y = You (POV learner, solves alongside F).
Total runtime target: 20:00. Running time (cumulative) noted after each scene.

COLD OPEN — 1:00
Scene
Type
Dur
Visual
Beat
Cumulative
S0
🎬 WAN
1:00
Deep-space listening post, dish array, control room hum, static bursts on a monitor
Alarm triggers. M: "We're picking up something. It's not noise — it's repeating." Signal waveform freezes on screen as pairs of numbers. Title card: THE SIGNAL
1:00


CHAPTER 1 — Complex Numbers ("Decoding the Signal") — 4:30
Scene
Type
Dur
Visual
Beat / Math tie-in
Cumulative
S1
🎬 WAN
1:00
Control room, three consoles. Screen shows raw bursts as pairs (a, b) scrolling
M poses problem: "Two numbers per burst. No units, no label. Is it one thing or two?" F turns to Y: "It's simpler than it looks." → sets up 1.1
2:00
S2
📐 Manim
1:00
Ordered pair (a,b) → point on grid → relabeled z = a+ib. One merge shown: (a,b)+(c,d)=(a+c,b+d)
Compresses 1.1 + 1.1b + 1.2 into one clean visual chain: raw pair → algebraic object → mergeable object
3:00
S3
🎬 WAN
1:00
F at whiteboard-screen, Y watching, two decoded fragments pulse on the main display
F: "Now we need two things from this — how strong it is, and which way it's pointing." Sets up 1.3 stakes conversationally, no equation yet
4:00
S4
📐 Manim
0:45
Right triangle forms from a, b on the complex plane → hypotenuse labeled `
z
→ angle labeledθ`
S5
🎬 WAN
0:45
Full Argand plane rendered as a starfield overlay on the ship's nav display; a single point locks in as a heading vector
Y: "That's... a direction." M: "That's our heading." Chapter payoff (1.4) — cliffhanger: "Getting there means turning. A lot."
5:30


CHAPTER 2 — De Moivre's Theorem ("Course Correction") — 3:30
Scene
Type
Dur
Visual
Beat / Math tie-in
Cumulative
S6
🎬 WAN
1:00
Ship exterior, thrusters firing in short repeated bursts, cockpit shaking slightly
M: "To match that bearing we rotate — dozens of times. We can't simulate each burn." Problem stated for 2.1
6:30
S7
📐 Manim
1:00
(cosθ+isinθ) rotating once → then jump-cut to rotated n times labeled nθ in one step
Delivers De Moivre's shortcut: one multiplication replaces n repeated rotations
7:30
S8
🎬 WAN
0:45
Radar sweep reveals not one but several signal sources arranged in a ring
F: "It's not one station. It's several — and they're evenly spaced." Sets up 2.2
8:15
S9
📐 Manim
0:45
zⁿ=1 → n points snap onto a unit circle, evenly spaced, animated as a "ping" per point
Delivers nth roots of unity as literally the relay-station layout
9:00


CHAPTER 3 — Quadratic Expressions ("The Burn Window") — 4:30
Scene
Type
Dur
Visual
Beat / Math tie-in
Cumulative
S10
🎬 WAN
1:00
Mission-control style screen, a curved trajectory line plotting distance vs. time toward the ring of stations
M: "Our path isn't straight — thrust and drift curve it. We need to know exactly when we arrive." Sets up 3.1
10:00
S11
📐 Manim
1:00
Parabola drawn from ax²+bx+c=0, roots highlighted where curve crosses zero, quadratic formula appears beside it
Delivers 3.1 cleanly: the curve is the trajectory, the formula finds arrival time
11:00
S12
🎬 WAN
0:45
Proximity alarm blips — trajectory line dips too close to a hazard marker on screen
F: "Does this ever go negative — a collision course? And where's the most efficient point to burn?" Tension beat for 3.2
11:45
S13
📐 Manim
0:45
Same parabola, vertex highlighted with a dot, shaded region below zero flagged red
Delivers vertex/max-min + sign rule — danger zone vs. optimal burn point, visually obvious
12:30
S14
🎬 WAN
1:00
Mission control overlays a green "safe corridor" band across the trajectory graph; ship executes the burn smoothly inside it
M: "Not one instant — a window." Burn succeeds, ship glides into the corridor. Chapter payoff (3.3)
13:30


CHAPTER 4 — Theory of Equations ("Cracking the Cipher") — 5:45
Scene
Type
Dur
Visual
Beat / Math tie-in
Cumulative
S15
🎬 WAN
1:00
Ship arrives at the ring; a final long polynomial string decrypts onto the main screen, characters lit by its glow
M: "This is it — the cipher. A full polynomial. Solving it outright will take too long." Sets up 4.1
14:30
S16
📐 Manim
1:00
Polynomial a₀xⁿ+...+aₙ=0 with arrows pulling out Σx₁ = -a₁/a₀ and x₁x₂...xₙ = (-1)ⁿaₙ/a₀
Delivers 4.1: coefficients → root facts, without solving
15:30
S17
🎬 WAN
0:45
Y spots a flagged annotation inside the cipher: "one coordinate = 2 × another"
F: "That's not noise — that's a clue." Sets up 4.2
16:15
S18
📐 Manim
0:45
Roots relabeled α, 2α, γ substituted into the sum/product equations, solving down to numbers
Delivers 4.2: the relation becomes an extra equation that pins down the roots
17:00
S19
🎬 WAN
0:45
Two decoded coordinates flicker, rendered with an imaginary component — crew exchanges an uneasy look
Y: "Some of these are complex. Is the data broken?" Tension beat for 4.3
17:45
S20
📐 Manim
0:30
z=p+iq and z̄=p-iq appear as mirrored points, snapping together as a pair — quick cut back to a small ghost image of the Ch.1 Argand plane
Delivers 4.3 fast, with the visual full-circle callback to Chapter 1
18:15
S21
🎬 WAN
1:00
Final transformation equation resolves on screen; coordinates lock in; the two symmetric relay stations reveal themselves visually as the true destination
M: "Shift it, scale it, invert it — the roots become coordinates." Climax of 4.4, mission cracked
19:15


RESOLUTION — 0:45
Scene
Type
Dur
Visual
Beat
Cumulative
S22
🎬 WAN
0:45
Ship approaches the source — two structures in perfect symmetry, exactly as predicted. Crew silent, then F and Y exchange a look. M, voice-over: "Every step got us here." Fade out on title card
Full-circle close — mission complete
20:00


