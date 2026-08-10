#!/usr/bin/env python3
"""probe.py — PROBE-THE-ORACLE for ship 011.

v4 mandates two things of an architect, in this order:
  (a) NEGATIVE CONTROLS — break the artifact the way the oracle claims to catch, and confirm the
      oracle goes RED. A predicate with no control that flips it is decoration.
  (b) AN INDEPENDENT BREAK ATTEMPT — try to construct an artifact that is wrong and that the
      oracle still passes. What that attempt finds shapes the oracle.

Both are below. Each control is a byte-level mutation of the BUILT page, served from a scratch copy
of public/, and each names the predicate it must turn red.

Honest note on method: the controls run at a smaller sample budget than oracle.py (512 spp rather
than 4096) so that ten mutations finish in minutes rather than hours. They call the SAME predicate
functions and the SAME tolerance constants from oracle.py; only the Monte-Carlo noise tolerance is
scaled, by exactly sqrt(4096/512), which is the noise model already derived in CONTRACT.md §3.
Nothing else differs, and no control is judged by a rule oracle.py does not use.

Usage: python3 oracles/011-diffusion-curves/probe.py
Exit 0 = every control flipped its predicate as claimed.
"""
import json, math, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oracle as O  # noqa: E402

SPP = 512
NOISE_SCALE = math.sqrt(O.P3_SAMPLES / SPP)
P3_TOL = O.P3_MEAN_TOL * NOISE_SCALE

# ---------------------------------------------------------------------------- mutations
# Each: (id, claim, [(find, replace), ...], predicate that MUST go red)
CONTROLS = [
    ("C1-nearest-colour",
     "replace the random walk with 'take the nearest boundary colour' — a Voronoi fill. Looks "
     "plausible, is not harmonic, and is deterministic.",
     [("'    if(d < EPS) return boundaryColour(idx, sgn);\\n' +",
       "'    if(true) return boundaryColour(idx, sgn);\\n' +")],
     "P3"),

    ("C2-affine-ramp",
     "THE CONSTRUCTED BREAK (see §Independent attempt): replace the field with a linear ramp. An "
     "affine function IS harmonic, so it satisfies the mean-value property exactly and P3 alone "
     "cannot see it. P2 must be what catches it.",
     [("'  vec3 c = a.a > 0.0 ? a.rgb / a.a : vec3(0.0);\\n' +",
       "'  vec3 c = vec3(gl_FragCoord.x / 512.0 + 0.2);\\n' +")],
     "P2"),

    ("C3-sides-swapped",
     "swap which side of each curve gets which colour. The field stays perfectly harmonic; only "
     "the boundary data is wrong.",
     [("'vec3 boundaryColour(int idx, float sgn){ return sgn > 0.0 ? uColR[idx] : uColL[idx]; }\\n' +",
       "'vec3 boundaryColour(int idx, float sgn){ return sgn > 0.0 ? uColL[idx] : uColR[idx]; }\\n' +")],
     "P2"),

    ("C4-seed-ignored",
     "ignore the caller's seed. Every render becomes the same sequence — the estimator is no "
     "longer stochastic in the way the page claims.",
     [("state.seed = (seed === undefined ? state.seed : seed) >>> 0;",
       "state.seed = 1;")],
     "P5.seed"),

    ("C5-frozen-image",
     "stop accumulating after 16 samples but keep the counter climbing. The page reports 4096 "
     "samples over a 16-sample image: the exact shape of a static asset pretending to converge.",
     [("    gl.drawArrays(gl.TRIANGLES, 0, 3);\n    cur = 1 - cur;\n    state.samples += spp;",
       "    if (state.samples <= 16) { gl.drawArrays(gl.TRIANGLES, 0, 3); cur = 1 - cur; }\n"
       "    state.samples += spp;")],
     "P4"),

    ("C6-seam-not-screen",
     "return a correct buffer from DC.pixels() while blanking the visible canvas. This is ship "
     "008's failure exactly — a verified seam over a dead deliverable — and P6 exists for it.",
     [("    pixels: function () { return Array.prototype.slice.call(readCanvas()); },",
       "    pixels: function () { if (!window.__snap) window.__snap = "
       "Array.prototype.slice.call(readCanvas()); gl.bindFramebuffer(gl.FRAMEBUFFER, null); "
       "gl.clearColor(0,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT); return window.__snap; },")],
     "P6"),

    ("C7-dead-button",
     "leave the automation seam fully working and make the Render button do nothing. Every "
     "predicate that talks to DC.* still passes.",
     [("  btnRender.addEventListener('click', function () {\n    var n = ",
       "  btnRender.addEventListener('click', function () {\n    if (1) return;\n    var n = ")],
     "P7"),

    ("C8-unescaped-label",
     "interpolate the caption straight into innerHTML.",
     [("capEl.innerHTML = '<span class=\"cap\">' + esc(s) + '</span>';",
       "capEl.innerHTML = '<span class=\"cap\">' + s + '</span>';")],
     "P9.escaping"),

    ("C9-2d-canvas",
     "take a 2D context on the canvas before the app runs, so the page cannot have WebGL at all "
     "and must fall back or fail.",
     [("<!-- ===== inlined verbatim from lib/esc.js ===== -->",
       "<script>document.addEventListener('DOMContentLoaded',function(){},false);"
       "window.addEventListener('load',function(){},false);</script>"
       "<script>document.write('');</script>"
       "<!-- ===== inlined verbatim from lib/esc.js ===== -->")],
     "SKIP"),   # replaced below by the direct form
]

# C9 needs to run BEFORE app.js takes the context; the cleanest byte-level way is to grab a 2D
# context in a script tag placed immediately before the engine block.
CONTROLS[-1] = (
    "C9-2d-canvas",
    "take a 2D context on the canvas before the engine runs, so getContext('webgl2') can only "
    "return null. A page that then claims to render is claiming something impossible.",
    [("<!-- ===== ship engine + UI (src/011-diffusion-curves/app.js) ===== -->",
      "<script>document.getElementById('dc-canvas').getContext('2d');</script>\n"
      "<!-- ===== ship engine + UI (src/011-diffusion-curves/app.js) ===== -->")],
    "P1")


# ---------------------------------------------------------------------------- harness
def stage(mutations):
    """Copy public/ to scratch and apply mutations to the ship page. Returns (dir, applied)."""
    d = tempfile.mkdtemp(prefix="probe011-")
    shutil.copytree(O.PUBLIC, os.path.join(d, "public"))
    page = os.path.join(d, "public", "011-diffusion-curves", "index.html")
    src = open(page, encoding="utf-8").read()
    for find, repl in mutations:
        if find not in src:
            shutil.rmtree(d, ignore_errors=True)
            raise SystemExit(f"MUTATION DID NOT APPLY — the probe is stale:\n  {find[:110]}")
        src = src.replace(find, repl, 1)
    open(page, "w", encoding="utf-8").write(src)
    return d


def measure(root, want_ui=False):
    """Run the small predicate battery against a staged copy. Returns a dict of results."""
    from playwright.sync_api import sync_playwright
    httpd, url = O.serve(os.path.join(root, "public"))
    out = {}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(
                executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                headless=False,
                args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            pg = b.new_page(viewport={"width": 1100, "height": 900})
            pg.goto(url + O.SHIP_PATH, wait_until="load")
            try:
                pg.wait_for_function("() => !!window.DC", timeout=20000)
            except Exception:
                out["P1"] = False
                b.close()
                return out

            m = pg.evaluate("""() => { const c = DC.canvas(); let gl=null, two=null;
                try { gl = c.getContext('webgl2'); } catch(e){}
                try { two = c.getContext('2d'); } catch(e){}
                return {backend: DC.meta().backend, gl: !!gl, two: !!two}; }""")
            out["P1"] = (m["backend"] == "webgl2") and m["gl"] and not m["two"]

            def render(scene, spp, seed):
                pg.evaluate("s => DC.load(s)", scene)
                pg.evaluate("o => { DC.render(o); }", {"samples": spp, "seed": seed})
                pg.wait_for_function("o => DC.meta().samples >= o.samples || !!DC.meta().error",
                                     arg={"samples": spp}, timeout=900000)
                if pg.evaluate("() => DC.meta().error"):
                    return None
                return pg.evaluate("() => DC.pixels()")

            small = dict(O.S2, width=128, height=128)
            buf = render(small, SPP, 11)
            if buf is None:
                b.close(); return out
            out["P2"] = O.boundary_ok(small, buf)
            d = O.mean_value_stats(small, buf)
            out["P3"] = bool(d) and (sum(d) / len(d)) <= P3_TOL
            out["_P3v"] = round(sum(d) / max(len(d), 1), 2)

            ref = render(small, SPP * 4, 101)
            lo = render(small, 64, 202)
            hi = render(small, 256, 303)
            if None not in (ref, lo, hi):
                e_lo, e_hi = O.rmse(lo, ref), O.rmse(hi, ref)
                r = e_lo / e_hi if e_hi > 1e-9 else 999.0
                out["P4"] = (O.P4_BAND[0] <= r <= O.P4_BAND[1]) and e_lo > 0.5
                out["_P4v"] = round(r, 2)

            a1 = render(small, 128, 1)
            a2 = render(small, 128, 2)
            out["P5.seed"] = O.rmse(a1, a2) > 0.3

            render(small, 256, 5)
            seam = pg.evaluate("() => DC.pixels()")
            im = O.canvas_image(pg, 128, 128)
            out["P6"] = O.rmse(seam, list(im.tobytes())) <= O.P6_TOL

            out["P9.escaping"] = pg.evaluate("""() => { DC.setLabel('<img src=x onerror=window.__p=1>');
                return !window.__p && !document.querySelector('img[onerror]'); }""")

            if want_ui:
                p2 = b.new_page(viewport={"width": 1100, "height": 900})
                p2.goto(url + O.SHIP_PATH, wait_until="load")
                p2.wait_for_selector("#dc-canvas")
                p2.select_option("#dc-example", "three")
                p2.fill("#dc-samples", "256")
                p2.click("#dc-render")
                try:
                    p2.wait_for_function(
                        "() => document.getElementById('dc-status').dataset.state === 'done'",
                        timeout=90000)
                    out["P7"] = True
                except Exception:
                    out["P7"] = False
            b.close()
    finally:
        httpd.shutdown()
    return out


def main():
    print("PROBE-THE-ORACLE — ship 011\n" + "=" * 62)
    baseline_dir = stage([])
    print("\nBASELINE (unmutated build) — every predicate must be GREEN or the controls prove nothing")
    base = measure(baseline_dir, want_ui=True)
    shutil.rmtree(baseline_dir, ignore_errors=True)
    print("  " + json.dumps(base))
    bad = [k for k, v in base.items() if not k.startswith("_") and v is not True]
    if bad:
        print(f"\nBASELINE IS NOT GREEN ({bad}) — controls below are meaningless. Stop.")
        return 2

    results = []
    for cid, claim, muts, target in CONTROLS:
        print(f"\n[{cid}] must turn {target} RED\n  {claim}")
        d = stage(muts)
        try:
            r = measure(d, want_ui=(target == "P7"))
        finally:
            shutil.rmtree(d, ignore_errors=True)
        got = r.get(target, None)
        flipped = (got is False) or (got is None and target != "P7")
        others = {k: v for k, v in r.items() if not k.startswith("_") and k != target}
        print(f"  {target} = {got!r}  -> {'RED as claimed' if flipped else 'DID NOT FLIP'}")
        print(f"  collateral: {json.dumps(others)}")
        results.append((cid, target, flipped, r))

    print("\n" + "=" * 62)
    print("INDEPENDENT BREAK ATTEMPT (v4 clause b), stated before the controls were written:")
    print("""
  Attempt A1 — 'pass P3 without solving anything.' The mean-value property is satisfied EXACTLY by
  any affine function, so a plain linear ramp is a perfect harmonic fake. This is a real hole in
  P3 and it is why S2 carries three curves whose two-sided colour data no affine function can
  match, and why P2 is a separate predicate rather than folded into P3. C2 is that attack, run.

  Attempt A2 — 'pass everything through the seam while the page is dead.' Ship 008 did this by
  accident. P6 (seam == screenshot) and P7 (drive the real buttons, never touch DC.*) were written
  for it before any code existed. C6 and C7 are that attack, run.

  Attempt A3 — 'pass P4 with a deterministic renderer by adding noise.' A faker could dither the
  output per seed and produce a 1/sqrt(N)-looking curve. This attempt SUCCEEDS against P4 alone.
  It fails against P3+P2 together, because dither is not harmonic and the dither amplitude needed
  to fake the convergence curve is the same amplitude P3 measures. Recorded as a known limit of
  P4 in isolation rather than patched, because the composite is already sound.

  Attempt A4 — 'satisfy P2 and P3 on the oracle's scenes only, by hard-coding them.' Not defended
  against by any predicate here, and honestly stated: the oracle's scenes are in a public repo.
  What makes it unrewarding rather than impossible is P7, which renders whatever scene the PAGE
  declares, and P5.scene, which requires a different scene to produce a different image. A build
  that hard-coded S1/S2/S3 would still have to solve the UI's own example. Left as a stated limit.
""")
    n_ok = sum(1 for _, _, f, _ in results if f)
    print("=" * 62)
    print(f"{n_ok}/{len(results)} controls flipped their predicate as claimed")
    for cid, target, f, _ in results:
        if not f:
            print(f"  NOT FLIPPED: {cid} -> {target}  (the predicate is decoration until fixed)")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
