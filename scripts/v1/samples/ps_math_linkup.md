"The Signal" — Problem → Equation → Why
For each sub-topic: the problem the crew hits, the exact equation that solves it, and why that's the right tool. Use this to stage each scene.

Chapter 1 — Complex Numbers ("Decoding the Signal")
1.1 Complex number as an ordered pair
Problem: The signal arrives as two raw numbers per burst — no unit, no label. The crew doesn't know if it's one quantity or two. Equation used: $z=(a,b)$ with equality rule $(a,b)=(c,d) \iff a=c,\ b=d$ Why this equation: It's the minimum structure needed to say "this pair is one object, not two separate numbers" — without it the crew can't even compare two bursts to see if they match.
1.1b Fundamental operations
Problem: Two overlapping fragments of the same burst need to be merged into one clean reading. Equation used: $(a,b)+(c,d)=(a+c,\ b+d)$ and $(a,b)\cdot(c,d)=(ac-bd,\ ad+bc)$ Why this equation: Addition merges two readings of the same kind; multiplication is needed once the crew starts combining a signal with a rotation (later chapter) — so both rules have to be nailed down now, before they're needed.
1.2 Representation as $a+ib$
Problem: The ship's computer can't log raw pairs — it needs a format it can print, compare, and feed into later calculations. Equation used: $z=a+ib$ Why this equation: It's the same object as $(a,b)$, just written so ordinary algebra (the kind the computer already runs) applies to it directly — no new machinery, just a translation.
1.3 Modulus and Amplitude
Problem: Crew needs two operational numbers out of the decoded signal: how strong is it, and which way is it pointing? Equation used: $|z|=\sqrt{a^2+b^2}$ (strength), $\theta=\tan^{-1}(b/a)$ (bearing) Why this equation: These are literally the only two numbers you can extract from a 2D point that mean "distance" and "direction" — Pythagoras gives distance, right-triangle trig gives angle. Nothing else in the toolkit produces those two facts.
1.4 Geometric/Polar representation, Argand diagram
Problem: The crew has numbers but no heading to feed the ship's navigation system. Equation used: $z=r(\cos\theta+i\sin\theta)$, plotted as point $(a,b)$ Why this equation: Polar form is a heading — magnitude + angle is exactly what a navigation system takes as input. This is the equation that turns math into an actual steering instruction.

Chapter 2 — De Moivre's Theorem ("Course Correction")
2.1 De Moivre's Theorem — integral & rational indices
Problem: Reaching the bearing needs dozens of small rotation burns in sequence. Simulating each one is too slow. Equation used: $(\cos\theta+i\sin\theta)^n=\cos n\theta+i\sin n\theta$ Why this equation: It replaces "apply the same rotation $n$ times" with one multiplication ($n\theta$). This is the one identity that turns repeated rotation into a single computation — exactly the shortcut the ship's computer needs.
2.2 nth roots of unity, geometric interpretation
Problem: The signal isn't from one source — it's coming from several stations, and the crew needs to know how many and where. Equation used: $z^n=1 \Rightarrow z=\cos\left(\frac{2k\pi}{n}\right)+i\sin\left(\frac{2k\pi}{n}\right)$ Why this equation: Solving $z^n=1$ is the only equation whose solution set is automatically "$n$ points, evenly spaced on a circle" — which is exactly the physical layout (a ring of relay stations) the crew is trying to locate.

Chapter 3 — Quadratic Expressions ("The Burn Window")
3.1 Quadratic expressions & equations in one variable
Problem: The ship's distance-to-target over time isn't a straight line — it curves, because thrust and drift both act on it. Crew needs to know when the ship reaches the target. Equation used: $ax^2+bx+c=0,\quad x=\dfrac{-b\pm\sqrt{b^2-4ac}}{2a}$ Why this equation: The distance-vs-time model comes out quadratic because acceleration is constant during a burn (same reason projectile motion is quadratic) — the quadratic formula is the direct solver for "when does this curve hit zero."
3.2 Sign of quadratic expressions, max/min values
Problem: Crew needs to know if the trajectory ever crosses into "collision" territory, and where the most fuel-efficient point of the burn is. Equation used: Vertex $x=-\dfrac{b}{2a}$, value $-\dfrac{D}{4a}$; sign matches $a$ outside the roots Why this equation: The vertex formula is the only way to find a turning point without calculus — and the sign rule tells the crew, without checking every single time value, whether the curve ever dips into the danger zone.
3.3 Quadratic inequations
Problem: Mission control doesn't want an exact instant — it wants a window of safe times/positions to burn in. Equation used: $a(x-\alpha)(x-\beta)<0 \iff \alpha<x<\beta$ (for $a>0$) Why this equation: An equation gives one instant; an inequation gives a range. Once the roots are known (from 3.1), this inequality is the direct translation of "stay between these two boundaries."

Chapter 4 — Theory of Equations ("Cracking the Cipher")
4.1 Relation between roots and coefficients
Problem: The cipher is a full polynomial — solving it outright is slow. Crew wants clues about the destination before fully cracking it. Equation used: $\sum x_1=-\dfrac{a_1}{a_0},\quad \sum x_1x_2=\dfrac{a_2}{a_0},\quad x_1x_2\cdots x_n=(-1)^n\dfrac{a_n}{a_0}$ Why this equation: These relations pull out facts about the roots (sum, product) directly from the coefficients already visible in the transmission — no need to solve the equation to get partial intel.
4.2 Solving equations when roots are connected by a relation
Problem: The cipher includes a hint that two coordinates are related (e.g. one is double another) — an extra constraint that should make solving easier, not harder. Equation used: Substitute the relation (e.g. roots $\alpha,2\alpha,\gamma$) into the sum/product formulas from 4.1 and solve simultaneously Why this equation: The relation is exactly one extra equation — combined with the root-coefficient relations, the system now has enough equations to pin down every root, instead of needing to factor blind.
4.3 Real coefficients — complex roots in conjugate pairs
Problem: Some decoded coordinates come out complex. Crew wants to know if that means the data is corrupted, or if it's meaningful. Equation used: If $a_i\in\mathbb{R}$ and $z=p+iq$ is a root, then $\bar z=p-iq$ is also a root Why this equation: Because the cipher's coefficients are real, this theorem guarantees complex roots come in pairs — telling the crew this isn't noise, it's proof the source is symmetric (two stations, not one).
4.4 Transformation of equations, reciprocal equations
Problem: The raw cipher's roots aren't the actual coordinates — they need to be shifted/scaled/inverted to reveal the true destination. Equation used: Replace $x \to x-h$ (shift), $x \to x/k$ (scale), or $x \to 1/x$ (invert) inside $f(x)=0$ to get a new equation Why this equation: Instead of re-solving from scratch, substitution builds a new equation whose roots are already the transformed values the crew needs — this is the direct mechanism that turns "cipher root" into "actual coordinate."

Use each row as a beat: state the problem in-story → have a character reach for the equation → have them say why nothing else would work.

