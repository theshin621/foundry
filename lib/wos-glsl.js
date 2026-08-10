/* lib/wos-glsl.js — the reusable piece extracted from ship 011 (diffusion curves).
 *
 * A grid-free **walk-on-spheres** estimator for the Laplace equation with two-sided Dirichlet
 * data on line segments, as a WebGL2 fragment shader plus the scene->uniform packing it needs.
 * Mechanism after Sawhney (CMU 2024), "Grid-Free Monte Carlo methods for PDEs"; the estimator is
 * per-pixel independent, which is why it is a fragment shader and not a solver.
 *
 * WHY THIS IS A SHARED PRIMITIVE: any future ship that needs a smooth field obeying boundary
 * data — gradient tools, heat maps, distance-field art, interpolation over sketched constraints —
 * needs exactly this and should not re-derive it. Ships stay self-contained, so a ship INLINES a
 * verbatim copy of SHADER_FS and packScene(); this file is the canonical source and the ship's
 * oracle carries a drift predicate (P10) asserting the inlined copy still matches this text.
 *
 * WHAT IT IS NOT: this is not a general PDE solver. Dirichlet data on segments only; no Neumann,
 * no source term, no anisotropy. The image border is a boundary too — callers must pass it, which
 * packScene() does, otherwise the problem is not well posed on a finite canvas.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WOS = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var MAX_SEG = 64;

  /* Scene -> flat uniform arrays.
   * scene = {width, height, curves:[{pts:[[x,y]...], left:[r,g,b], right:[r,g,b]}]}
   * Coordinates are normalised [0,1], origin top-left, y DOWN.
   * "left" is the side where the 2-D cross product (b-a) x (p-a) is NEGATIVE in y-down space.
   * The four border segments are appended with left == right == bg, which both closes the domain
   * and gives the caller a background tint for free.
   */
  function packScene(scene, bg) {
    var seg = [], colL = [], colR = [], i, j, c, p;
    for (i = 0; i < scene.curves.length; i++) {
      c = scene.curves[i]; p = c.pts;
      for (j = 0; j + 1 < p.length; j++) {
        if (seg.length / 4 >= MAX_SEG) break;
        seg.push(p[j][0], p[j][1], p[j + 1][0], p[j + 1][1]);
        colL.push(c.left[0] / 255, c.left[1] / 255, c.left[2] / 255);
        colR.push(c.right[0] / 255, c.right[1] / 255, c.right[2] / 255);
      }
    }
    var b = [(bg && bg[0] || 0) / 255, (bg && bg[1] || 0) / 255, (bg && bg[2] || 0) / 255];
    var border = [[0, 0, 1, 0], [1, 0, 1, 1], [1, 1, 0, 1], [0, 1, 0, 0]];
    for (i = 0; i < 4; i++) {
      if (seg.length / 4 >= MAX_SEG) break;
      seg.push(border[i][0], border[i][1], border[i][2], border[i][3]);
      colL.push(b[0], b[1], b[2]);
      colR.push(b[0], b[1], b[2]);
    }
    return { n: seg.length / 4, seg: new Float32Array(seg), colL: new Float32Array(colL),
             colR: new Float32Array(colR) };
  }

  var SHADER_VS = '#version 300 es\n' +
    'in vec2 aPos; void main(){ gl_Position = vec4(aPos,0.0,1.0); }\n';

  /* Accumulation pass. Reads the running sum, adds uSPP fresh walks, writes sum + count.
   * RGBA32F: rgb = sum of boundary colours hit, a = number of walks. */
  var SHADER_FS = '#version 300 es\n' +
    'precision highp float; precision highp int;\n' +
    'uniform sampler2D uPrev;\n' +
    'uniform vec2  uRes;\n' +
    'uniform int   uNSeg;\n' +
    'uniform vec4  uSeg[' + MAX_SEG + '];\n' +
    'uniform vec3  uColL[' + MAX_SEG + '];\n' +
    'uniform vec3  uColR[' + MAX_SEG + '];\n' +
    'uniform uint  uSeed;\n' +
    'uniform int   uSPP;\n' +
    'uniform int   uBase;\n' +
    'out vec4 outC;\n' +
    'const int MAXSTEP = 40;\n' +
    'const float EPS = 0.0015;\n' +
    'uint hashu(uint x){ x^=x>>16; x*=0x7feb352du; x^=x>>15; x*=0x846ca68bu; x^=x>>16; return x; }\n' +
    'float rnd(inout uint s){ s = s*747796405u + 2891336453u;\n' +
    '  uint r = ((s >> ((s >> 28) + 4u)) ^ s) * 277803737u; r = (r >> 22) ^ r;\n' +
    '  return float(r) * (1.0/4294967296.0); }\n' +
    // nearest boundary point: distance, which segment, and which side we are on
    'void closest(vec2 p, out float d, out int idx, out float sgn){\n' +
    '  d = 1e9; idx = 0; sgn = 1.0;\n' +
    '  for(int i=0;i<uNSeg;i++){\n' +
    '    vec4 s = uSeg[i]; vec2 a = s.xy, b = s.zw;\n' +
    '    vec2 v = b-a, w = p-a;\n' +
    '    float L2 = dot(v,v);\n' +
    '    float t = L2 > 0.0 ? clamp(dot(w,v)/L2, 0.0, 1.0) : 0.0;\n' +
    '    float dd = length(p - (a + t*v));\n' +
    '    if(dd < d){ d = dd; idx = i; sgn = v.x*(p.y-a.y) - v.y*(p.x-a.x); }\n' +
    '  }\n' +
    '}\n' +
    'vec3 boundaryColour(int idx, float sgn){ return sgn > 0.0 ? uColR[idx] : uColL[idx]; }\n' +
    // one walk-on-spheres path: jump to a uniform point on the largest empty ball until the
    // boundary is within EPS, then take the colour of the side we arrived on.
    'vec3 walk(vec2 p, inout uint st){\n' +
    '  float d; int idx; float sgn;\n' +
    '  for(int k=0;k<MAXSTEP;k++){\n' +
    '    closest(p, d, idx, sgn);\n' +
    '    if(d < EPS) return boundaryColour(idx, sgn);\n' +
    '    float th = 6.28318530718 * rnd(st);\n' +
    '    p += d * vec2(cos(th), sin(th));\n' +
    '  }\n' +
    '  closest(p, d, idx, sgn); return boundaryColour(idx, sgn);\n' +
    '}\n' +
    'void main(){\n' +
    '  ivec2 ip = ivec2(gl_FragCoord.xy);\n' +
    '  vec2 uv = (gl_FragCoord.xy) / uRes;\n' +
    '  vec2 p  = vec2(uv.x, 1.0 - uv.y);\n' +           // gl_FragCoord is bottom-up; scene is y-down
    '  uint st = hashu(uint(ip.x) + uint(ip.y)*1973u + uSeed*9277u + uint(uBase)*26699u);\n' +
    '  vec3 sum = vec3(0.0);\n' +
    '  for(int i=0;i<uSPP;i++) sum += walk(p, st);\n' +
    '  vec4 prev = texelFetch(uPrev, ip, 0);\n' +
    '  outC = vec4(prev.rgb + sum, prev.a + float(uSPP));\n' +
    '}\n';

  /* Display pass: mean of the accumulated walks. */
  var SHADER_SHOW = '#version 300 es\n' +
    'precision highp float;\n' +
    'uniform sampler2D uAcc;\n' +
    'out vec4 outC;\n' +
    'void main(){\n' +
    '  vec4 a = texelFetch(uAcc, ivec2(gl_FragCoord.xy), 0);\n' +
    '  vec3 c = a.a > 0.0 ? a.rgb / a.a : vec3(0.0);\n' +
    '  outC = vec4(clamp(c, 0.0, 1.0), 1.0);\n' +
    '}\n';

  return { MAX_SEG: MAX_SEG, packScene: packScene,
           SHADER_VS: SHADER_VS, SHADER_FS: SHADER_FS, SHADER_SHOW: SHADER_SHOW };
});
