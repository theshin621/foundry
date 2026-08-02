/* lib/esc.js — the ONE HTML-escape helper every ship uses on any user-derived string
 * before it reaches innerHTML. Inline a copy into each ship (pages stay self-contained);
 * this file is the canonical source.
 *
 * WHY THIS IS A SHARED PRIMITIVE (2026-08-02): ship 002 shipped TWO security findings in
 * two checker rounds, both the same class — a user-controlled string reaching innerHTML
 * unescaped. Round 1: a value interpolated into a template. Round 2: a value interpolated
 * into a THROWN ERROR MESSAGE, then rendered. The lesson is not "remember to escape" — it
 * is "route every sink through one audited function and escape at the boundary". If a ship
 * builds HTML from input, it uses this. The checker greps for raw `innerHTML=` assignments
 * that don't pass through esc().
 *
 * Escapes the five characters that matter in both element and attribute context. It does
 * NOT make arbitrary input safe inside a <script>, a style, a URL, or an unquoted attribute
 * — those need context-specific handling and are out of scope on purpose.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.esc = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return MAP[c]; });
  };
});
