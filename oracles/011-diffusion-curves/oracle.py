#!/usr/bin/env python3
"""oracle.py — ship 011 diffusion-curve renderer.

Written BEFORE the artifact (oracle-before-code, v4 / BOTTLENECKS #1). Read CONTRACT.md first.

It does not read the artifact's source. It starts a real Chromium, loads the page over HTTP, and
observes behaviour — because a static reader cannot tell a solver from a blur, and BOTTLENECKS #1's
third clause forbids the hand-written parse-and-match band that killed #006/#007/#008/#009.

Usage:
    python3 oracles/011-diffusion-curves/oracle.py [--url URL] [--json]

Exit 0 = all predicates PASS. Exit 1 = at least one FAIL. Exit 2 = could not run at all.
"""
import argparse, base64, io, json, math, os, random, subprocess, sys, time, threading
import http.server, socketserver, functools

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PUBLIC = os.path.join(REPO, "public")
SHIP_PATH = "/011-diffusion-curves/"

# ---------------------------------------------------------------- tolerances
# P3_TOL derivation (see CONTRACT.md §3). u is a bounded average of boundary colours, so a
# single-sample estimate of one channel has sd <= 127.5 (worst case: half the walks land on 0,
# half on 255). With S samples per pixel the per-pixel standard error is <= 127.5/sqrt(S).
# P3 compares one centre pixel against the mean of K=64 circle pixels; the circle mean's noise is
# smaller by sqrt(64)=8, so the difference is dominated by the centre: sd_diff ~ 127.5/sqrt(S).
# At the P3 reference S=4096 that is ~2.0 levels. A 3-sigma per-probe band is ~6.0.
# We additionally average |diff| over many probes, which shrinks the statistic further, so the
# MEAN bound is set at 6.0 and the per-probe MAX bound at 22.0 (>3 sigma, still far under any
# non-harmonic field's error -- the probe's blur control lands at 30+).
P3_SAMPLES = 4096
P3_MEAN_TOL = 6.0
P3_MAX_TOL = 22.0
P2_TOL = 26.0        # boundary probes sit 3px off the curve; a little bleed is physical
P4_BAND = (1.4, 3.2)  # RMSE(N)/RMSE(4N), ideal 2.0
P6_TOL = 4.0          # seam vs screenshot, allows PNG/colour-space rounding only
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"          # seam vs screenshot, allows PNG/colour-space rounding only

# ---------------------------------------------------------------- test scenes (oracle-owned)
# S1: two horizontal curves, deliberately the EASY case (used for P2/P4/P5).
# S2: three curves whose colour data cannot be satisfied by any affine function of (x,y) --
#     this is what makes P2+P3 jointly unfakeable by a linear ramp (probe attack A2).
S1 = {
    "width": 192, "height": 192,
    "curves": [
        {"pts": [[0.05, 0.30], [0.95, 0.30]], "left": [255, 40, 40], "right": [30, 60, 220]},
        {"pts": [[0.05, 0.72], [0.95, 0.72]], "left": [40, 220, 90], "right": [240, 210, 40]},
    ],
}
S2 = {
    "width": 192, "height": 192,
    "curves": [
        {"pts": [[0.12, 0.18], [0.88, 0.22]], "left": [250, 60, 20], "right": [20, 40, 200]},
        {"pts": [[0.15, 0.80], [0.85, 0.78]], "left": [30, 200, 120], "right": [230, 220, 40]},
        {"pts": [[0.50, 0.34], [0.52, 0.66]], "left": [250, 250, 250], "right": [10, 10, 10]},
    ],
}
S3 = {  # a third, structurally different scene for P5 "responds to input"
    "width": 192, "height": 192,
    "curves": [
        {"pts": [[0.20, 0.20], [0.80, 0.20], [0.80, 0.80], [0.20, 0.80], [0.20, 0.20]],
         "left": [255, 255, 0], "right": [0, 0, 255]},
    ],
}


# ---------------------------------------------------------------- geometry (oracle's own, in python)
def segments(scene):
    out = []
    for c in scene["curves"]:
        p = c["pts"]
        for i in range(len(p) - 1):
            out.append((p[i], p[i + 1], c["left"], c["right"]))
    return out


def dist_point_seg(px, py, a, b):
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def dist_to_scene(px, py, scene):
    return min(dist_point_seg(px, py, s[0], s[1]) for s in segments(scene))


def side_of(px, py, a, b):
    """>0 right, <0 left, in a y-down coordinate system (CONTRACT §1)."""
    return (b[0] - a[0]) * (py - a[1]) - (b[1] - a[1]) * (px - a[0])


# ---------------------------------------------------------------- pixel helpers
def px_at(buf, w, x, y):
    i = (y * w + x) * 4
    return (buf[i], buf[i + 1], buf[i + 2])


def rmse(a, b):
    n = min(len(a), len(b))
    s = 0.0
    cnt = 0
    for i in range(0, n, 4):          # RGB only, skip alpha
        for k in range(3):
            d = a[i + k] - b[i + k]
            s += d * d
            cnt += 1
    return math.sqrt(s / max(cnt, 1))



def mean_value_stats(scene, buf):
    """|u(p) - mean of u on a circle of radius r about p|, for interior p whose whole disc is
    clear of every boundary. Zero for a harmonic function; large for a blur or an interpolation."""
    W_ = scene["width"]
    rnd = random.Random(20260810)
    diffs, tries = [], 0
    while len(diffs) < 60 and tries < 4000:
        tries += 1
        x = rnd.uniform(0.12, 0.88)
        y = rnd.uniform(0.12, 0.88)
        r = rnd.uniform(0.035, 0.075)
        if dist_to_scene(x, y, scene) < r * 1.25:
            continue
        if x - r < 0.02 or x + r > 0.98 or y - r < 0.02 or y + r > 0.98:
            continue
        centre = px_at(buf, W_, int(x * W_), int(y * W_))
        acc = [0.0, 0.0, 0.0]
        K = 64
        for i in range(K):
            th = 2 * math.pi * i / K
            p = px_at(buf, W_, int((x + r * math.cos(th)) * W_), int((y + r * math.sin(th)) * W_))
            for k in range(3):
                acc[k] += p[k]
        diffs.append(max(abs(acc[k] / K - centre[k]) for k in range(3)))
    return diffs


def boundary_probes(scene, buf, off=0.016):
    """(total, bad, worst) over points just off each segment, on a known side.

    The offset is in DOMAIN units, not pixels, and that is a correction rather than a preference.
    The first version used 3 pixels, which is 0.0156 of the domain at 192x192 and 0.0234 at
    128x128 -- so the predicate silently asked a harder question at lower resolution. Measured
    2026-08-10 on the same build: at 192 it read worst-error 18, at 128 it read 27, and the
    difference is not defect, it is the harmonic solution genuinely drifting toward the other
    boundary data as you step further (in domain units) off the curve. A predicate whose meaning
    depends on the resolution cannot be interpreted, so it is denominated in the domain.
    """
    W_ = scene["width"]
    bad = tot = 0
    worst = 0.0
    for (a, b, lc, rc) in segments(scene):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        for sgn in (+1, -1):
            qx, qy = mx + sgn * nx * off, my + sgn * ny * off
            if dist_to_scene(qx, qy, scene) < off * 0.8:
                continue
            want = rc if side_of(qx, qy, a, b) > 0 else lc
            got = px_at(buf, W_, int(qx * W_), int(qy * W_))
            err = max(abs(got[k] - want[k]) for k in range(3))
            worst = max(worst, err)
            tot += 1
            if err > P2_TOL:
                bad += 1
    return tot, bad, worst


def boundary_ok(scene, buf):
    tot, bad, _ = boundary_probes(scene, buf)
    return tot >= 4 and bad == 0



def canvas_image(page, w, h):
    """A byte-faithful picture of what the canvas element is DISPLAYING.

    Not `locator.screenshot()`: that captures the element's border box, so a 1px CSS border and a
    fractional page offset come along for the ride (measured 2026-08-10: a 128x128 canvas shown at
    384 CSS px came back 385x385 at y=182.0625, and resampling that to 128 gave RMSE 10.4 against
    the identical pixels read straight off the canvas). Clipping to the CONTENT box and resizing
    nearest-neighbour -- the canvas is `image-rendering: pixelated`, so every displayed pixel is
    exactly one canvas pixel -- gives RMSE 0.0. The border was an artefact of the instrument, and
    the fix is to the instrument, not to the tolerance.
    """
    from PIL import Image
    box = page.evaluate("""() => { const c = document.getElementById('dc-canvas');
        const r = c.getBoundingClientRect();
        return {x: r.left + c.clientLeft, y: r.top + c.clientTop,
                width: c.clientWidth, height: c.clientHeight}; }""")
    im = Image.open(io.BytesIO(page.screenshot(clip=box))).convert("RGBA")
    if im.size != (w, h):
        im = im.resize((w, h), Image.NEAREST)
    return im


# ---------------------------------------------------------------- local server
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root):
    handler = functools.partial(_Quiet, directory=root)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------- the run
def run(url, verbose=True):
    from playwright.sync_api import sync_playwright

    R = []          # (id, ok, detail)
    def rec(pid, ok, detail):
        R.append((pid, bool(ok), detail))
        if verbose:
            print(f"  [{'PASS' if ok else 'FAIL'}] {pid}: {detail}")

    net = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            headless=False,
            args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        )
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.on("request", lambda r: net.append(r.url))
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + SHIP_PATH, wait_until="load")
        page.wait_for_function("() => !!window.DC", timeout=20000)

        # ---------------- P1 real graphics pipeline
        p1 = page.evaluate("""() => {
            const m = DC.meta(), c = DC.canvas();
            let gl = null, two = null;
            try { gl = c.getContext('webgl2'); } catch(e) {}
            try { two = c.getContext('2d'); } catch(e) {}
            return {backend: m.backend, hasGL: !!gl, has2D: !!two,
                    isCanvas: (c instanceof HTMLCanvasElement), inDom: document.body.contains(c)};
        }""")
        rec("P1.backend", p1["backend"] == "webgl2", f"DC.meta().backend={p1['backend']!r}")
        rec("P1.gl", p1["hasGL"] and not p1["has2D"],
            f"canvas webgl2={p1['hasGL']} 2d={p1['has2D']} (a 2D fake cannot have both)")
        rec("P1.onscreen", p1["isCanvas"] and p1["inDom"], f"canvas in DOM={p1['inDom']}")

        def render(scene, samples, seed):
            page.evaluate("s => DC.load(s)", scene)
            # deliberately NOT awaited: page.evaluate() would await the returned promise
            # against Playwright's 30s default and time out on a slow software render.
            page.evaluate("o => { DC.render(o); }", {"samples": samples, "seed": seed})
            # a render that dies (WebGL context loss) sets DC.meta().error; wait for either so a
            # dead render is a FAIL with a reason, not an opaque timeout.
            page.wait_for_function("o => DC.meta().samples >= o.samples || !!DC.meta().error",
                                   arg={"samples": samples}, timeout=900000)
            err = page.evaluate("() => DC.meta().error")
            if err:
                raise RuntimeError("render aborted: " + str(err))
            return page.evaluate("() => DC.pixels()")

        # ---------------- P2 Dirichlet boundary data
        buf = render(S2, 1024, 11)
        tot, bad, worst = boundary_probes(S2, buf)
        rec("P2.dirichlet", tot >= 4 and bad == 0,
            f"{tot-bad}/{tot} boundary probes within {P2_TOL} (worst channel error {worst:.1f})")

        # ---------------- P3 harmonic / mean-value property
        buf3 = render(S2, P3_SAMPLES, 7)
        d = mean_value_stats(S2, buf3)
        mean_d = sum(d) / max(len(d), 1)
        max_d = max(d) if d else 999
        rec("P3.meanvalue.count", len(d) >= 30, f"{len(d)} interior probes placed")
        rec("P3.meanvalue.mean", mean_d <= P3_MEAN_TOL,
            f"mean |u(p) - avg_circle| = {mean_d:.2f} (tol {P3_MEAN_TOL})")
        rec("P3.meanvalue.max", max_d <= P3_MAX_TOL,
            f"max |u(p) - avg_circle| = {max_d:.2f} (tol {P3_MAX_TOL})")

        buf3b = render(S1, P3_SAMPLES, 8)
        d2 = mean_value_stats(S1, buf3b)
        m2 = sum(d2) / max(len(d2), 1)
        rec("P3.meanvalue.scene2", len(d2) >= 20 and m2 <= P3_MEAN_TOL,
            f"second scene mean = {m2:.2f} over {len(d2)} probes")

        # ---------------- P4 Monte Carlo convergence
        ref = render(S1, 2048, 101)
        lo = render(S1, 128, 202)
        hi = render(S1, 512, 303)
        e_lo, e_hi = rmse(lo, ref), rmse(hi, ref)
        ratio = e_lo / e_hi if e_hi > 1e-9 else 999.0
        rec("P4.converges", P4_BAND[0] <= ratio <= P4_BAND[1],
            f"RMSE(128)={e_lo:.2f} RMSE(512)={e_hi:.2f} ratio={ratio:.2f} "
            f"(ref 2048 spp; ideal 1.84 after ref noise, band {P4_BAND})")
        rec("P4.nonzero", e_lo > 0.5, f"low-sample RMSE {e_lo:.2f} > 0.5 (a static image gives 0)")

        # ---------------- P5 responds to inputs
        a1 = render(S1, 256, 1)
        a2 = render(S1, 256, 2)
        a3 = render(S1, 256, 1)
        b1 = render(S3, 256, 1)
        rec("P5.seed", rmse(a1, a2) > 0.3, f"seed 1 vs 2 RMSE {rmse(a1,a2):.2f} > 0.3")
        rec("P5.reproducible", a1 == a3, "same seed+samples reproduces byte-identically")
        rec("P5.scene", rmse(a1, b1) > 8.0, f"scene S1 vs S3 RMSE {rmse(a1,b1):.2f} > 8.0")

        # ---------------- P6 seam == screen
        render(S2, 1024, 5)
        seam = page.evaluate("() => DC.pixels()")
        im = canvas_image(page, S2["width"], S2["height"])
        got = list(im.tobytes())
        e6 = rmse(seam, got)
        rec("P6.seam_is_screen", e6 <= P6_TOL,
            f"DC.pixels() vs browser screenshot of the visible canvas: RMSE {e6:.2f} (tol {P6_TOL})")

        # ---------------- P7 the human path, with NO DC.* call
        page2 = browser.new_page(viewport={"width": 1100, "height": 900})
        errors2 = []
        page2.on("pageerror", lambda e: errors2.append(str(e)))
        page2.goto(url + SHIP_PATH, wait_until="load")
        page2.wait_for_selector("#dc-canvas")
        page2.select_option("#dc-example", "three")     # the S2-shaped built-in example
        # A DISTINCTIVE sample count, and the status line must end up quoting it.
        # WHY: the first version of P7 clicked Render and waited for status=done. The page renders
        # once on load by itself, so status was ALREADY done and the wait returned instantly --
        # a completely dead Render button passed P7. The probe's C7 control caught this (it did
        # not flip) and this is the fix: the click must produce a render at a sample count the
        # page's own auto-render cannot have produced.
        UI_SPP = "1536"
        page2.fill("#dc-samples", UI_SPP)
        page2.click("#dc-render")
        page2.wait_for_function("() => document.getElementById('dc-status')"
                                ".dataset.state === 'running'", timeout=30000)
        page2.wait_for_function("() => document.getElementById('dc-status')"
                                ".dataset.state === 'done'", timeout=600000)
        ui_status = page2.text_content("#dc-status") or ""
        rec("P7.click_caused_it", UI_SPP + " samples" in ui_status,
            f"status after clicking Render reads {ui_status.strip()[:70]!r} "
            f"(must quote the {UI_SPP} the human typed, not the page's own startup render)")
        scn = json.loads(page2.get_attribute("#dc-canvas", "data-scene"))
        im2 = canvas_image(page2, scn["width"], scn["height"])
        ui_buf = list(im2.tobytes())
        d7 = mean_value_stats(scn, ui_buf)
        m7 = sum(d7) / max(len(d7), 1)
        rec("P7.ui_harmonic", len(d7) >= 20 and m7 <= P3_MEAN_TOL * 1.6,
            f"UI-driven canvas (no DC.* call) mean-value error {m7:.2f} over {len(d7)} probes")
        tot7, bad7, _w7 = boundary_probes(scn, ui_buf)
        rec("P7.ui_dirichlet", tot7 >= 4 and bad7 == 0,
            f"UI-driven canvas honours boundary data: {tot7-bad7}/{tot7}")

        # ---------------- P8 export
        with page2.expect_download(timeout=60000) as dl:
            page2.click("#dc-export")
        path = dl.value.path()
        with open(path, "rb") as f:
            raw = f.read()
        ok8 = raw[:8] == PNG_MAGIC and len(raw) > 1000
        det8 = f"{len(raw)} bytes, PNG magic {'ok' if raw[:8] == PNG_MAGIC else 'BAD'}"
        if ok8:
            from PIL import Image
            pim = Image.open(io.BytesIO(raw)).convert("RGBA")
            if pim.size != im2.size:
                pim = pim.resize(im2.size, Image.NEAREST)
            e8 = rmse(list(pim.tobytes()), ui_buf)
            ok8 = e8 <= 8.0
            det8 += f", RMSE vs on-screen canvas {e8:.2f} (tol 8.0)"
        rec("P8.export", ok8, det8)

        # ---------------- P9 hygiene
        third = [u for u in net if not u.startswith(url) and not u.startswith("data:")
                 and not u.startswith("blob:")]
        rec("P9.no_third_party", not third, f"third-party requests: {third[:4] or 'none'}")
        rec("P9.no_pageerrors", not errors and not errors2,
            f"uncaught page errors: {(errors + errors2)[:3] or 'none'}")
        xss = page.evaluate("""() => {
            // feed a hostile label through whatever path renders user text
            const probe = '<img src=x onerror=window.__pwned=1>';
            if (typeof DC.setLabel === 'function') DC.setLabel(probe);
            return {pwned: !!window.__pwned,
                    injected: !!document.querySelector('img[onerror]')};
        }""")
        rec("P9.escaping", not xss["pwned"] and not xss["injected"],
            f"hostile label did not become markup ({xss})")

        # ---------------- P11 a scene swap MID-RENDER must not contaminate the result
        # Added after the round-1 checker found that changing the example while a render was in
        # flight kept accumulating the NEW boundary data into the OLD buffer, then reported
        # "done" over a blend of two different boundary-value problems (centre-pixel error 62,
        # ~3x P2's tolerance). Every predicate above was blind to it because P7 selects its
        # example once, before clicking Render. Driven entirely through the UI: no DC.* call.
        def ui_render(pg, example, spp):
            pg.select_option("#dc-example", example)
            pg.fill("#dc-samples", str(spp))
            pg.click("#dc-render")
            pg.wait_for_function("() => document.getElementById('dc-status')"
                                 ".dataset.state === 'done'", timeout=600000)
            scn_ = json.loads(pg.get_attribute("#dc-canvas", "data-scene"))
            return scn_, list(canvas_image(pg, scn_["width"], scn_["height"]).tobytes())

        pgA = browser.new_page(viewport={"width": 1100, "height": 900})
        pgA.goto(url + SHIP_PATH, wait_until="load")
        pgA.wait_for_selector("#dc-canvas")
        scn_c, clean = ui_render(pgA, "loop", 1024)

        pgB = browser.new_page(viewport={"width": 1100, "height": 900})
        pgB.goto(url + SHIP_PATH, wait_until="load")
        pgB.wait_for_selector("#dc-canvas")
        pgB.select_option("#dc-example", "three")
        pgB.fill("#dc-samples", "6000")
        pgB.click("#dc-render")
        pgB.wait_for_function("() => document.getElementById('dc-status')"
                              ".dataset.state === 'running'", timeout=30000)
        time.sleep(12)                      # let a real partial average build up
        scn_s, swapped = ui_render(pgB, "loop", 1024)   # swap mid-flight, then render for real
        e11 = rmse(clean, swapped)
        d11 = mean_value_stats(scn_s, swapped)
        m11 = sum(d11) / max(len(d11), 1)
        # two independent 1024-spp renders of the same scene differ by MC noise alone:
        # sqrt(2) * 127.5/sqrt(1024) ~ 5.6 worst case. 14 leaves headroom and is far under the
        # 62-level contamination the checker measured.
        rec("P11.midrender_swap_clean", e11 <= 14.0,
            f"scene swapped mid-render then rendered: RMSE vs a clean render of the same scene "
            f"= {e11:.2f} (tol 14.0; contamination measured at 62 before the fix)")
        rec("P11.midrender_swap_harmonic", len(d11) >= 20 and m11 <= P3_MEAN_TOL * 1.6,
            f"and the result is still harmonic: mean-value error {m11:.2f} over {len(d11)} probes")
        pgA.close(); pgB.close()

        # ---------------- P10 the inlined shared primitives have not drifted from lib/
        try:
            r10 = subprocess.run([sys.executable, os.path.join(REPO, "tools", "build-011.py"),
                                  "--check"], capture_output=True, text=True, timeout=60)
            rec("P10.no_drift", r10.returncode == 0,
                (r10.stdout + r10.stderr).strip()[:160] or f"exit {r10.returncode}")
        except Exception as e:
            rec("P10.no_drift", False, f"{type(e).__name__}: {e}")

        browser.close()
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None, help="base URL; default: serve public/ locally")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    httpd = None
    try:
        if a.url:
            url = a.url.rstrip("/")
        else:
            httpd, url = serve(PUBLIC)
        t0 = time.time()
        R = run(url, verbose=not a.json)
    except Exception as e:
        print(f"ORACLE COULD NOT RUN: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        if httpd:
            httpd.shutdown()
    npass = sum(1 for _, ok, _ in R if ok)
    if a.json:
        print(json.dumps([{"id": i, "ok": o, "detail": d} for i, o, d in R], indent=1))
    print(f"\n{npass}/{len(R)} predicates PASS  ({time.time()-t0:.0f}s)")
    fails = [i for i, o, _ in R if not o]
    if fails:
        print("FAILED: " + ", ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
