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
            page.evaluate("o => DC.render(o)", {"samples": samples, "seed": seed})
            page.wait_for_function("o => DC.meta().samples >= o.samples",
                                   arg={"samples": samples}, timeout=180000)
            return page.evaluate("() => DC.pixels()")

        # ---------------- P2 Dirichlet boundary data
        W = S2["width"]
        buf = render(S2, 1024, 11)
        off = 3.0 / W
        bad, tot, worst = 0, 0, 0.0
        for (a, b, lc, rc) in segments(S2):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / L, dx / L          # a normal
            for sgn, want in ((+1, None), (-1, None)):
                qx, qy = mx + sgn * nx * off, my + sgn * ny * off
                want = rc if side_of(qx, qy, a, b) > 0 else lc
                if dist_to_scene(qx, qy, S2) < off * 0.8:
                    continue                   # too close to another curve to attribute
                got = px_at(buf, W, int(qx * W), int(qy * W))
                err = max(abs(got[k] - want[k]) for k in range(3))
                worst = max(worst, err)
                tot += 1
                if err > P2_TOL:
                    bad += 1
        rec("P2.dirichlet", tot >= 4 and bad == 0,
            f"{tot-bad}/{tot} boundary probes within {P2_TOL} (worst channel error {worst:.1f})")

        # ---------------- P3 harmonic / mean-value property
        def mean_value_stats(scene, buf):
            W_ = scene["width"]
            rnd = random.Random(20260810)
            diffs = []
            tries = 0
            while len(diffs) < 60 and tries < 4000:
                tries += 1
                x = rnd.uniform(0.12, 0.88)
                y = rnd.uniform(0.12, 0.88)
                r = rnd.uniform(0.035, 0.075)
                if dist_to_scene(x, y, scene) < r * 1.25:
                    continue
                if x - r < 0.02 or x + r > 0.98 or y - r < 0.02 or y + r > 0.98:
                    continue
                cx, cy = int(x * W_), int(y * W_)
                centre = px_at(buf, W_, cx, cy)
                acc = [0.0, 0.0, 0.0]
                K = 64
                for i in range(K):
                    th = 2 * math.pi * i / K
                    sx = int((x + r * math.cos(th)) * W_)
                    sy = int((y + r * math.sin(th)) * W_)
                    p = px_at(buf, W_, sx, sy)
                    for k in range(3):
                        acc[k] += p[k]
                diffs.append(max(abs(acc[k] / K - centre[k]) for k in range(3)))
            return diffs

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
        ref = render(S1, 8192, 101)
        lo = render(S1, 128, 202)
        hi = render(S1, 512, 303)
        e_lo, e_hi = rmse(lo, ref), rmse(hi, ref)
        ratio = e_lo / e_hi if e_hi > 1e-9 else 999.0
        rec("P4.converges", P4_BAND[0] <= ratio <= P4_BAND[1],
            f"RMSE(128)={e_lo:.2f} RMSE(512)={e_hi:.2f} ratio={ratio:.2f} "
            f"(expect ~2.0, band {P4_BAND})")
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
        shot = page.locator("#dc-canvas").screenshot()
        from PIL import Image
        im = Image.open(io.BytesIO(shot)).convert("RGBA")
        sw, sh = im.size
        got = list(im.tobytes())
        if (sw, sh) != (S2["width"], S2["height"]):
            im = im.resize((S2["width"], S2["height"]), Image.NEAREST)
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
        page2.fill("#dc-samples", "2048")
        page2.click("#dc-render")
        page2.wait_for_function("() => document.getElementById('dc-status')"
                                ".dataset.state === 'done'", timeout=240000)
        shot2 = page2.locator("#dc-canvas").screenshot()
        im2 = Image.open(io.BytesIO(shot2)).convert("RGBA")
        scn = json.loads(page2.get_attribute("#dc-canvas", "data-scene"))
        w2, h2 = im2.size
        if (w2, h2) != (scn["width"], scn["height"]):
            im2 = im2.resize((scn["width"], scn["height"]), Image.NEAREST)
        ui_buf = list(im2.tobytes())
        d7 = mean_value_stats(scn, ui_buf)
        m7 = sum(d7) / max(len(d7), 1)
        rec("P7.ui_harmonic", len(d7) >= 20 and m7 <= P3_MEAN_TOL * 1.6,
            f"UI-driven canvas (no DC.* call) mean-value error {m7:.2f} over {len(d7)} probes")
        W7 = scn["width"]
        bad7 = tot7 = 0
        for (a, b, lc, rc) in segments(scn):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / L, dx / L
            for sgn in (+1, -1):
                qx, qy = mx + sgn * nx * (3.0 / W7), my + sgn * ny * (3.0 / W7)
                if dist_to_scene(qx, qy, scn) < (3.0 / W7) * 0.8:
                    continue
                want = rc if side_of(qx, qy, a, b) > 0 else lc
                got_p = px_at(ui_buf, W7, int(qx * W7), int(qy * W7))
                tot7 += 1
                if max(abs(got_p[k] - want[k]) for k in range(3)) > P2_TOL:
                    bad7 += 1
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
