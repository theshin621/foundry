# Oracle contract — ship 011 · diffusion-curve gradient renderer

**Written 2026-08-10 by the ARCHITECT before a single line of the artifact existed.** The artifact is
built to this file; this file is not adjusted to the artifact. (BOTTLENECKS #1: *"an oracle fixes the
target set before the first line is written, so the defect count can actually converge."*)

## 0. What is being claimed, stated so it can be falsified

The page solves the **Laplace equation** Δu = 0 on the image domain, with **two-sided Dirichlet data**
supplied by a set of curves (each curve carries a `left` and a `right` colour), using **grid-free
walk-on-spheres** — a per-pixel-independent Monte Carlo estimator — executed **on the GPU pipeline in
a real browser**.

Four things could each be false, and each is a separate predicate:

1. it isn't running in the graphics pipeline at all (a 2D-canvas or CSS fake);
2. it doesn't honour the boundary data (pretty, wrong);
3. **the field it produces is not harmonic** — a blur, a distance-weighted blend, or an inverse-
   distance interpolation looks extremely similar to the eye and is not a solution;
4. it isn't actually a Monte Carlo estimator (a static image, or a deterministic fake that never
   converges).

## 1. The automation seam the artifact MUST expose

`window.DC`, present after `DOMContentLoaded`:

| member | signature | meaning |
|---|---|---|
| `DC.load(scene)` | `(sceneObject) => void` | replace the current scene |
| `DC.render(opts)` | `({samples, seed}) => Promise<void>` | resolves only when the render for exactly `samples` samples is complete |
| `DC.pixels()` | `() => number[]` | RGBA bytes of the **current framebuffer**, length `w*h*4` |
| `DC.meta()` | `() => ({backend, width, height, samples, seed})` | `backend` must be the literal string `webgl2` |
| `DC.canvas()` | `() => HTMLCanvasElement` | the **on-screen** canvas — the same element the user sees |

Scene object:

```json
{ "width": 256, "height": 256,
  "curves": [ { "pts": [[x,y], ...], "left": [r,g,b], "right": [r,g,b] } ] }
```

`x,y` are normalised to `[0,1]`, origin top-left, `y` down. `left` is the side reached by turning
**left** from the segment direction — i.e. the side on which the 2-D cross product
`(b-a) × (p-a)` is **negative** in a y-down coordinate system. Colours are 0–255 sRGB.

**The seam is not the deliverable.** P6 and P7 exist specifically to bind the seam to the pixels a
human sees and to the buttons a human clicks. Ship #008 passed a module-level oracle while being
inert on every real page; that failure mode is designed against here rather than hoped away.

## 2. Predicates (all must hold — the oracle reports per-predicate)

- **P1 · real graphics pipeline.** `DC.meta().backend === "webgl2"`, **and** independently:
  `DC.canvas().getContext("webgl2")` is non-null **and** `DC.canvas().getContext("2d")` is null.
  A canvas can only ever have one context type, so this pair cannot both hold for a 2D fake.
- **P2 · Dirichlet boundary data honoured.** For probe points placed a few pixels off each curve, on
  a known side, the rendered colour matches that side's declared colour.
- **P3 · the field is harmonic (the mean-value property).** For interior points `p` at distance
  `≥ r` from every curve, `u(p)` equals the average of `u` over the circle of radius `r` about `p`.
  This is the *definition* of harmonic and is what separates a solver from a blur.
  **Scene design note, and the reason S2 exists:** an affine ramp is harmonic, so P3 alone can be
  satisfied by a global linear gradient. The harmonic scenes therefore carry **≥3 curves with
  non-collinear, non-affine-satisfiable colour data**, so P2 and P3 together admit no linear fake.
  This break was constructed against the oracle before the artifact existed (see `probe.py` A2).
- **P4 · it is genuinely Monte Carlo.** Error against a high-sample reference must fall like
  `1/sqrt(samples)`: `RMSE(N) / RMSE(4N)` lands in `[1.4, 3.2]` (ideal 2.0). A static image or a
  deterministic fake gives ≈1.0; a broken estimator gives noise that does not converge.
- **P5 · it responds to its inputs.** Different `seed` ⇒ different pixels. Different scene ⇒
  different pixels. Same seed and samples ⇒ **byte-identical** pixels (reproducibility).
- **P6 · the seam shows what the screen shows.** `DC.pixels()` agrees with a screenshot of
  `DC.canvas()` taken by the browser itself.
- **P7 · the human path drives the same renderer.** Playwright loads the page, clicks the real
  controls, and the resulting on-screen canvas satisfies P2 and P3 — **with no `DC.*` call at any
  point.** If P7 fails while P1–P6 pass, the seam is a parallel implementation and the ship is a lie.
- **P8 · export is real.** The PNG the download button produces decodes, and its pixels match the
  canvas.
- **P9 · hygiene.** No third-party network request. Text derived from user input is escaped
  (`lib/esc.js`). Page is self-contained.

## 3. Tolerances, and how they were set

Tolerances are calibrated **against the oracle's own noise model, not against the artifact's output**
— an oracle tuned until the build passes is decoration. `P3_TOL` is derived from the measured
per-pixel Monte Carlo standard error at the reference sample count and stated in `oracle.py` as a
constant with its derivation in a comment. If a negative control cannot be made to fail a predicate,
the predicate is deleted, not loosened.

## 4. What this oracle does NOT prove

- It does not prove the renderer is *fast*, or that WebGPU-class quality is reached.
- It runs on SwiftShader (software WebGL2) in this container. It proves the **GL path executes and is
  correct**; it does not prove behaviour on any particular vendor's driver.
- P4 assumes the estimator is Monte Carlo by design. A hypothetical exact solver would fail P4 while
  being *better*. That is a deliberate, stated limit: the claim under test is the card's claim.
