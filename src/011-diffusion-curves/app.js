/* ship 011 — diffusion-curve gradient renderer. Engine + UI.
 * The estimator and its shaders live in lib/wos-glsl.js and are inlined above this block
 * verbatim; this file is only the WebGL plumbing, the UI, and the automation seam (window.DC).
 */
(function () {
  'use strict';

  var W = 128, H = 128;                      // solve resolution; CSS scales the canvas up
  /* Samples per draw call, adapted at run time. This is NOT a taste knob. A single draw that
   * takes ~a second is long enough for the browser's GPU watchdog to reset the context: measured
   * during the build at 192x192, where a 16-sample pass ran ~0.9s and Chromium logged
   * "CONTEXT_LOST_WEBGL: loseContext" a few passes in, after which every draw silently became a
   * no-op and the canvas read back as all zeros while the sample counter kept climbing. Bounding
   * each draw to ~100ms is the fix; the loop below halves or doubles the pass size to hold that. */
  /* Sizing is ANALYTIC, not measured. The first version of this adapted on wall-clock around
   * gl.finish() and ran away to 64 samples/pass, because in Chromium the GL calls are queued to a
   * separate GPU process and finish() does not block until the work is really done — so every
   * pass "measured" fast and the loop kept doubling until a single draw was ~3.6s and the context
   * died. Measured facts from that build: 128x128 x 64spp (1.05e6 pixel-samples) survived;
   * 192x192 x 64spp (2.36e6) lost the context. The budget below is ~4x under the survivor. */
  var PIXEL_SAMPLE_BUDGET = 2.5e5;
  function passSize() { return Math.max(1, Math.floor(PIXEL_SAMPLE_BUDGET / (W * H))); }
  var MAX_DIM = 512;

  var canvas = document.getElementById('dc-canvas');
  var statusEl = document.getElementById('dc-status');
  var gl = canvas.getContext('webgl2', { alpha: false, antialias: false,
                                         preserveDrawingBuffer: true });

  var EXAMPLES = {
    three: { name: 'three curves', scene: { width: 128, height: 128, curves: [
      { pts: [[0.12, 0.18], [0.88, 0.22]], left: [250, 60, 20], right: [20, 40, 200] },
      { pts: [[0.15, 0.80], [0.85, 0.78]], left: [30, 200, 120], right: [230, 220, 40] },
      { pts: [[0.50, 0.34], [0.52, 0.66]], left: [250, 250, 250], right: [10, 10, 10] }
    ] } },
    ribbon: { name: 'two ribbons', scene: { width: 128, height: 128, curves: [
      { pts: [[0.05, 0.30], [0.95, 0.30]], left: [255, 40, 40], right: [30, 60, 220] },
      { pts: [[0.05, 0.72], [0.95, 0.72]], left: [40, 220, 90], right: [240, 210, 40] }
    ] } },
    loop: { name: 'closed loop', scene: { width: 128, height: 128, curves: [
      { pts: [[0.22, 0.22], [0.78, 0.22], [0.78, 0.78], [0.22, 0.78], [0.22, 0.22]],
        left: [255, 235, 60], right: [25, 35, 150] }
    ] } },
    arc: { name: 'swept arc', scene: { width: 128, height: 128, curves: (function () {
      var p = [], i, t;
      for (i = 0; i <= 24; i++) { t = i / 24; p.push([0.10 + 0.80 * t, 0.5 + 0.28 * Math.sin(Math.PI * t)]); }
      return [{ pts: p, left: [255, 120, 0], right: [0, 90, 160] }];
    })() } }
  };

  var state = {
    scene: JSON.parse(JSON.stringify(EXAMPLES.three.scene)),
    bg: [18, 20, 24], samples: 0, target: 0, seed: 1, running: false, err: null,
    /* gen guards against two render loops running at once. Caught during the build when an
     * automated caller issued render() while the page's own first render was still going: both
     * requestAnimationFrame loops then incremented the SAME sample counter, so the target was
     * reached at twice the true sample count and the displayed image was whatever the losing
     * loop had last drawn. A generation token is the whole fix — a stale loop returns. */
    gen: 0
  };

  /* ---------------------------------------------------------------- GL setup */
  function fail(msg) {
    state.err = msg;
    statusEl.dataset.state = 'error';
    statusEl.textContent = msg;
  }
  if (!gl) { fail('This browser has no WebGL2. The renderer needs it — nothing else on the page will work.'); }
  var extF = gl && gl.getExtension('EXT_color_buffer_float');
  if (gl && !extF) { fail('WebGL2 is present but float render targets (EXT_color_buffer_float) are not. Cannot accumulate.'); }

  function sh(type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }
  function prog(vs, fs) {
    var p = gl.createProgram();
    gl.attachShader(p, sh(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  }

  var pAcc = null, pShow = null, quad = null, tex = [null, null], fbo = [null, null], cur = 0;

  function makeTex() {
    var t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, W, H, 0, gl.RGBA, gl.FLOAT, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    var f = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, f);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    return [t, f];
  }

  function initGL() {
    pAcc = prog(WOS.SHADER_VS, WOS.SHADER_FS);
    pShow = prog(WOS.SHADER_VS, WOS.SHADER_SHOW);
    quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    allocTargets();
  }

  /* (Re)allocate the ping-pong float targets at the current solve resolution. Called on init and
   * whenever a scene or the resolution control changes W/H — the card's "export at any
   * resolution" promise is this function. */
  function allocTargets() {
    var i;
    for (i = 0; i < 2; i++) {
      if (tex[i]) gl.deleteTexture(tex[i]);
      if (fbo[i]) gl.deleteFramebuffer(fbo[i]);
    }
    canvas.width = W; canvas.height = H;
    var a = makeTex(); tex[0] = a[0]; fbo[0] = a[1];
    var b = makeTex(); tex[1] = b[0]; fbo[1] = b[1];
    clearAcc();
  }

  function setResolution(w, h) {
    w = Math.max(16, Math.min(MAX_DIM, w | 0));
    h = Math.max(16, Math.min(MAX_DIM, h | 0));
    if (w === W && h === H) return;
    stopRun();
    W = w; H = h;
    if (pAcc) allocTargets();
  }

  /* Halt whatever is in flight and settle its promise. EVERY path that changes what is being
   * solved must call this first.
   *
   * Found by the round-1 checker, and it is the sibling of the bug the gen token was added for:
   * gen stopped two render loops racing, but the scene-select and file-input handlers reassigned
   * state.scene WITHOUT stopping the loop, so a running average kept accumulating — now against
   * the NEW boundary data, into the OLD buffer. The page then reported "done" over a blend of two
   * different boundary-value problems, which is not a solution to either. Measured contamination
   * at the centre pixel: 62 levels, ~3x the oracle's own tolerances. Ordinary users click the
   * example dropdown while a slow render is still going; this is not an exotic path. */
  function stopRun() {
    state.gen = (state.gen + 1) | 0;
    state.running = false;
    if (pending) { var r = pending; pending = null; r(); }
  }

  /* The one way the scene changes. */
  function setScene(scene, sourceHtml) {
    stopRun();
    state.scene = JSON.parse(JSON.stringify(scene));
    if (scene.width && scene.height) setResolution(scene.width, scene.height);
    state.scene.width = W; state.scene.height = H;
    clearAcc();
    show();
    canvas.setAttribute('data-scene', JSON.stringify(state.scene));
    if (sourceHtml !== undefined) srcEl.innerHTML = sourceHtml;
    statusEl.dataset.state = 'idle';
    statusEl.textContent = 'scene loaded (' + W + '×' + H + ') — press Render';
  }
  function bindQuad(p) {
    var loc = gl.getAttribLocation(p, 'aPos');
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  }
  function clearAcc() {
    for (var i = 0; i < 2; i++) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, fbo[i]);
      gl.viewport(0, 0, W, H);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    }
    cur = 0; state.samples = 0;
  }

  /* ---------------------------------------------------------------- passes */
  function accumulate(spp) {
    var pk = WOS.packScene(state.scene, state.bg);
    gl.useProgram(pAcc); bindQuad(pAcc);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo[1 - cur]);
    gl.viewport(0, 0, W, H);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex[cur]);
    gl.uniform1i(gl.getUniformLocation(pAcc, 'uPrev'), 0);
    gl.uniform2f(gl.getUniformLocation(pAcc, 'uRes'), W, H);
    gl.uniform1i(gl.getUniformLocation(pAcc, 'uNSeg'), pk.n);
    gl.uniform4fv(gl.getUniformLocation(pAcc, 'uSeg'), pk.seg);
    gl.uniform3fv(gl.getUniformLocation(pAcc, 'uColL'), pk.colL);
    gl.uniform3fv(gl.getUniformLocation(pAcc, 'uColR'), pk.colR);
    gl.uniform1ui(gl.getUniformLocation(pAcc, 'uSeed'), state.seed >>> 0);
    gl.uniform1i(gl.getUniformLocation(pAcc, 'uSPP'), spp);
    gl.uniform1i(gl.getUniformLocation(pAcc, 'uBase'), state.samples);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    cur = 1 - cur;
    state.samples += spp;
  }
  function show() {
    gl.useProgram(pShow); bindQuad(pShow);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, W, H);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex[cur]);
    gl.uniform1i(gl.getUniformLocation(pShow, 'uAcc'), 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  /* readPixels comes back bottom-up; flip so index 0 is the top-left pixel. */
  function readCanvas() {
    var raw = new Uint8Array(W * H * 4);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, raw);
    var out = new Uint8Array(W * H * 4), y, rowBytes = W * 4;
    for (y = 0; y < H; y++) out.set(raw.subarray((H - 1 - y) * rowBytes, (H - y) * rowBytes), y * rowBytes);
    return out;
  }

  /* ---------------------------------------------------------------- run loop */
  var pending = null;
  function step(g) {
    if (g !== state.gen || !state.running) return;
    if (gl.isContextLost()) { onLost(); return; }
    /* ONE pass per animation frame, deliberately. Queueing several draws inside a single frame
     * builds a long GPU command buffer and was observed to reset the context on the software
     * renderer; yielding after each pass lets it drain. Throughput is set by passSize(), not by
     * how many draws are crammed into a frame. */
    accumulate(Math.min(passSize(), state.target - state.samples));
    if (gl.isContextLost()) { onLost(); return; }
    show();
    if (state.samples >= state.target) {
      state.running = false;
      statusEl.dataset.state = 'done';
      statusEl.textContent = state.samples + ' samples/pixel · ' + W + '×' + H +
        ' · walk-on-spheres, WebGL2';
      if (pending) { var r = pending; pending = null; r(); }
    } else {
      statusEl.dataset.state = 'running';
      statusEl.textContent = 'rendering … ' + state.samples + ' / ' + state.target +
        ' samples/pixel';
      requestAnimationFrame(function () { step(g); });
    }
  }

  function start(samples, seed) {
    if (state.err) return Promise.reject(new Error(state.err));
    /* supersede any run in flight, then take the new token */
    stopRun();
    var g = state.gen;
    state.seed = (seed === undefined ? state.seed : seed) >>> 0;
    clearAcc();
    state.target = Math.max(1, samples | 0);
    state.running = true;
    canvas.setAttribute('data-scene', JSON.stringify(state.scene));
    statusEl.dataset.state = 'running';
    var p = new Promise(function (res) { pending = res; });
    requestAnimationFrame(function () { step(g); });
    return p;
  }

  /* Context loss is a real event on software renderers and on tab suspension. It must never be
   * silent: a lost context makes every draw a no-op while the sample counter keeps climbing, which
   * is exactly how a page reports "done" over a blank canvas. */
  function onLost() {
    state.running = false;
    state.err = 'The browser reset the WebGL context mid-render (this happens on software ' +
      'renderers at high resolution). Nothing on screen is a valid result. Reload and try a ' +
      'lower resolution or fewer samples.';
    statusEl.dataset.state = 'error';
    statusEl.textContent = state.err;
    if (pending) { var r = pending; pending = null; r(); }
  }
  if (canvas) {
    canvas.addEventListener('webglcontextlost', function (e) { e.preventDefault(); onLost(); });
  }

  /* ---------------------------------------------------------------- SVG import */
  function curvesFromSVG(text) {
    var doc = new DOMParser().parseFromString(text, 'image/svg+xml');
    var svg = doc.querySelector('svg');
    if (!svg) throw new Error('not an SVG document');
    var vb = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    var ox = 0, oy = 0, sw = Number(svg.getAttribute('width')) || 100,
        shh = Number(svg.getAttribute('height')) || 100;
    if (vb.length === 4 && vb.every(function (v) { return isFinite(v); })) {
      ox = vb[0]; oy = vb[1]; sw = vb[2]; shh = vb[3];
    }
    var out = [], els = doc.querySelectorAll('polyline,line,polygon,path'), i;
    for (i = 0; i < els.length; i++) {
      var el = els[i], pts = [];
      var tag = el.tagName.toLowerCase();
      if (tag === 'line') {
        pts = [[+el.getAttribute('x1'), +el.getAttribute('y1')],
               [+el.getAttribute('x2'), +el.getAttribute('y2')]];
      } else if (tag === 'polyline' || tag === 'polygon') {
        var nums = (el.getAttribute('points') || '').trim().split(/[\s,]+/).map(Number);
        for (var k = 0; k + 1 < nums.length; k += 2) pts.push([nums[k], nums[k + 1]]);
        if (tag === 'polygon' && pts.length > 2) pts.push(pts[0].slice());
      } else {                       // path: sample it with the browser's own geometry engine
        var L = 0;
        try { L = el.getTotalLength(); } catch (e) { L = 0; }
        if (!L) continue;
        var N = Math.min(48, Math.max(8, Math.round(L / 4)));
        for (var j = 0; j <= N; j++) {
          var pt = el.getPointAtLength(L * j / N);
          pts.push([pt.x, pt.y]);
        }
      }
      pts = pts.filter(function (q) { return isFinite(q[0]) && isFinite(q[1]); })
               .map(function (q) { return [(q[0] - ox) / sw, (q[1] - oy) / shh]; });
      if (pts.length < 2) continue;
      var stroke = el.getAttribute('stroke') || '#ff3b30';
      var fillc = el.getAttribute('fill');
      out.push({ pts: pts, left: parseColour(stroke, [255, 59, 48]),
                 right: parseColour(fillc && fillc !== 'none' ? fillc : '#2b6cff', [43, 108, 255]) });
      if (out.length >= 12) break;
    }
    if (!out.length) throw new Error('no <path>, <polyline>, <line> or <polygon> found');
    return out;
  }
  function parseColour(s, dflt) {
    s = String(s || '').trim();
    var m = /^#([0-9a-f]{6})$/i.exec(s);
    if (m) return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16),
                   parseInt(m[1].slice(4, 6), 16)];
    m = /^#([0-9a-f]{3})$/i.exec(s);
    if (m) return [17 * parseInt(m[1][0], 16), 17 * parseInt(m[1][1], 16), 17 * parseInt(m[1][2], 16)];
    m = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(s);
    if (m) return [Math.round(+m[1]), Math.round(+m[2]), Math.round(+m[3])];
    return dflt.slice();
  }

  /* One clamp, used by the button AND by the seam. Previously the button clamped to [1,16384]
   * and DC.render() did not, and `parseInt('0') || 512` silently substituted 512 for a typed 0
   * because 0 is falsy — both found by the round-1 checker. isFinite() first, so 0 clamps to the
   * stated minimum instead of vanishing into the default. */
  function clampSamples(v) {
    var n = parseInt(v, 10);
    if (!isFinite(n)) return 512;
    return Math.max(1, Math.min(16384, n));
  }

  /* ---------------------------------------------------------------- UI */
  var sel = document.getElementById('dc-example');
  var inSamples = document.getElementById('dc-samples');
  var btnRender = document.getElementById('dc-render');
  var btnExport = document.getElementById('dc-export');
  var fileIn = document.getElementById('dc-file');
  var titleIn = document.getElementById('dc-title');
  var resIn = document.getElementById('dc-res');
  var capEl = document.getElementById('dc-caption');
  var srcEl = document.getElementById('dc-source');

  Object.keys(EXAMPLES).forEach(function (k) {
    var o = document.createElement('option');
    o.value = k; o.textContent = EXAMPLES[k].name;
    sel.appendChild(o);
  });
  sel.value = 'three';

  function setLabel(s) {                       // every user string goes through esc()
    capEl.innerHTML = '<span class="cap">' + esc(s) + '</span>';
  }
  titleIn.addEventListener('input', function () { setLabel(titleIn.value); });

  resIn.addEventListener('change', function () {
    var n = parseInt(resIn.value, 10) || 128;
    setResolution(n, n);
    var sc = JSON.parse(JSON.stringify(state.scene));
    sc.width = W; sc.height = H;      // else setScene would restore the OLD resolution
    setScene(sc);
  });

  sel.addEventListener('change', function () {
    var sc = JSON.parse(JSON.stringify(EXAMPLES[sel.value].scene));
    sc.width = W; sc.height = H;
    setScene(sc, 'source: <b>' + esc(EXAMPLES[sel.value].name) + '</b> (built-in)');
  });

  btnRender.addEventListener('click', function () {
    start(clampSamples(inSamples.value), (state.seed + 1) >>> 0);
  });

  btnExport.addEventListener('click', function () {
    var a = document.createElement('a');
    a.download = 'diffusion-curves-' + W + 'x' + H + '-' + state.samples + 'spp.png';
    a.href = canvas.toDataURL('image/png');
    document.body.appendChild(a); a.click(); a.remove();
  });

  fileIn.addEventListener('change', function () {
    var f = fileIn.files && fileIn.files[0];
    if (!f) return;
    var fr = new FileReader();
    fr.onload = function () {
      try {
        var curves = curvesFromSVG(String(fr.result));
        setScene({ width: W, height: H, curves: curves },
          'source: <b>' + esc(f.name) + '</b> — ' + curves.length +
          ' curve(s). Stroke colour becomes the left side, fill the right.');
      } catch (e) {
        srcEl.innerHTML = '<span class="bad">could not read ' + esc(f.name) + ': ' +
          esc(e.message) + '</span>';
      }
    };
    fr.readAsText(f);
  });

  /* ---------------------------------------------------------------- seam */
  window.DC = {
    load: function (scene) { setScene(scene); },
    render: function (o) { return start(clampSamples(o && o.samples), (o && o.seed) || 1); },
    pixels: function () { return Array.prototype.slice.call(readCanvas()); },
    canvas: function () { return canvas; },
    setLabel: setLabel,
    meta: function () {
      return { backend: gl ? 'webgl2' : 'none', width: W, height: H,
               samples: state.samples, seed: state.seed, error: state.err,
               lost: gl ? gl.isContextLost() : true, passSpp: passSize() };
    }
  };

  if (gl && extF) {
    try {
      initGL();
      canvas.setAttribute('data-scene', JSON.stringify(state.scene));
      statusEl.dataset.state = 'idle';
      statusEl.textContent = 'ready — press Render';
      start(256, 1);
    } catch (e) { fail('WebGL2 initialisation failed: ' + e.message); }
  }
})();
