/* lib/mini-yaml.js — dependency-free YAML-subset parser.
 * Contributed by ship 002 (gha-trigger). Ships INLINE a copy (pages stay self-contained);
 * this file is the canonical source — fix bugs here, then re-inline.
 *
 * Scope: the subset real config files use — nested block maps, block sequences,
 * flow sequences [a, b], flow maps {a: b}, quoted scalars, comments, block scalars (| and >).
 *
 * DELIBERATE: scalars are NEVER coerced to booleans/numbers. This is not laziness —
 * YAML 1.1 parses the bare key `on` as boolean true, which is exactly the key every
 * GitHub Actions workflow uses. Keeping everything a string sidesteps that trap.
 * Callers coerce what they need.
 *
 * Tolerant by design: it must not throw on the parts of a document it doesn't care about
 * (e.g. `run:` blocks full of shell). Unparseable lines are skipped, not fatal.
 *
 * SECURITY — read before rendering an error: thrown messages QUOTE THE OFFENDING INPUT
 * so the user can find the line. That input is untrusted. Any caller putting e.message
 * into innerHTML must escape it first. Escaping is the sink's job, not the parser's —
 * the parser cannot know whether its message lands in HTML, a log, or a terminal.
 * (Ship 002 shipped this sink unescaped once; the checker caught it. Don't re-arm it.)
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.miniYAML = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Strip a trailing comment, respecting quotes. Returns the code part.
  function stripComment(line) {
    var out = '', q = null;
    for (var i = 0; i < line.length; i++) {
      var c = line[i];
      if (q) {
        out += c;
        if (c === q && line[i - 1] !== '\\') q = null;
      } else if (c === '"' || c === "'") {
        q = c; out += c;
      } else if (c === '#' && (i === 0 || /\s/.test(line[i - 1]))) {
        break;
      } else out += c;
    }
    return out.replace(/\s+$/, '');
  }

  function indentOf(line) {
    var m = line.match(/^[ ]*/);
    return m ? m[0].length : 0;
  }

  function unquote(s) {
    s = s.trim();
    if (s.length >= 2) {
      var a = s[0], b = s[s.length - 1];
      if ((a === '"' && b === '"') || (a === "'" && b === "'")) {
        var inner = s.slice(1, -1);
        return a === '"' ? inner.replace(/\\"/g, '"').replace(/\\n/g, '\n') : inner.replace(/''/g, "'");
      }
    }
    return s;
  }

  // ---- flow collections: [a, b] and {a: b} -------------------------------
  function splitFlow(s) {
    var parts = [], depth = 0, q = null, cur = '';
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      if (q) { cur += c; if (c === q) q = null; continue; }
      if (c === '"' || c === "'") { q = c; cur += c; continue; }
      if (c === '[' || c === '{') { depth++; cur += c; continue; }
      if (c === ']' || c === '}') { depth--; cur += c; continue; }
      if (c === ',' && depth === 0) { parts.push(cur); cur = ''; continue; }
      cur += c;
    }
    if (cur.trim() !== '') parts.push(cur);
    return parts;
  }

  function parseFlow(s) {
    s = s.trim();
    if (s[0] === '[' && s[s.length - 1] === ']') {
      var inner = s.slice(1, -1).trim();
      if (inner === '') return [];
      return splitFlow(inner).map(function (p) { return parseFlow(p); });
    }
    if (s[0] === '{' && s[s.length - 1] === '}') {
      var body = s.slice(1, -1).trim(), obj = {};
      if (body === '') return obj;
      splitFlow(body).forEach(function (p) {
        var idx = findColon(p);
        if (idx === -1) { obj[unquote(p)] = null; return; }
        obj[unquote(p.slice(0, idx))] = parseFlow(p.slice(idx + 1));
      });
      return obj;
    }
    // A bare leading * or & is a YAML alias/anchor, not a glob. GitHub rejects the file;
    // so do we, rather than silently treating '**/x.md' as a pattern it never was.
    if ((s[0] === '*' || s[0] === '&') && s.length > 1) {
      // Echo a bounded excerpt: enough to locate the line, not enough to flood a caller's UI.
      var q = s.length > 60 ? s.slice(0, 60) + '…' : s;
      throw new Error('unquoted ' + q + ' — YAML reads a leading * as an alias and & as an anchor. Quote it: "' + q + '"');
    }
    return unquote(s);
  }

  // Index of the key/value colon (a colon followed by space or end), outside quotes.
  function findColon(s) {
    var q = null;
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      if (q) { if (c === q) q = null; continue; }
      if (c === '"' || c === "'") { q = c; continue; }
      if (c === ':' && (i + 1 >= s.length || /[\s]/.test(s[i + 1]))) return i;
    }
    return -1;
  }

  // ---- block parsing -----------------------------------------------------
  // lines: [{indent, text}] ; parses the block at `base` indent starting at i.
  function parseBlock(lines, i, base, state) {
    // Decide sequence vs map by the first line of the block.
    if (i >= lines.length) return [null, i];
    if (lines[i].text[0] === '-' && (lines[i].text.length === 1 || lines[i].text[1] === ' ')) {
      return parseSeq(lines, i, base, state);
    }
    return parseMap(lines, i, base, state);
  }

  function parseSeq(lines, i, base, state) {
    var arr = [];
    while (i < lines.length) {
      var ln = lines[i];
      if (ln.indent < base) break;
      if (ln.indent > base) { i++; continue; } // stray deeper line — tolerate
      if (!(ln.text[0] === '-' && (ln.text.length === 1 || ln.text[1] === ' '))) break;
      var rest = ln.text.slice(1).trim();
      if (rest === '') {
        // value lives on following deeper lines
        var j = i + 1;
        if (j < lines.length && lines[j].indent > base) {
          var r = parseBlock(lines, j, lines[j].indent, state);
          arr.push(r[0]); i = r[1];
        } else { arr.push(null); i++; }
      } else {
        var colon = findColon(rest);
        if (colon !== -1) {
          // inline map entry starting the item: "- name: x" (+ possibly more keys below)
          var itemIndent = base + 2;
          var synthetic = [{ indent: itemIndent, text: rest }];
          var k = i + 1;
          while (k < lines.length && lines[k].indent > base) { synthetic.push(lines[k]); k++; }
          var norm = synthetic.map(function (s, idx) {
            return idx === 0 ? s : { indent: s.indent < itemIndent ? itemIndent : s.indent, text: s.text };
          });
          var m = parseMap(norm, 0, itemIndent, state);
          arr.push(m[0]); i = k;
        } else {
          arr.push(parseFlow(rest)); i++;
        }
      }
    }
    return [arr, i];
  }

  function parseMap(lines, i, base, state) {
    var obj = {};
    while (i < lines.length) {
      var ln = lines[i];
      if (ln.indent < base) break;
      if (ln.indent > base) { i++; continue; }
      if (ln.text[0] === '-' && (ln.text.length === 1 || ln.text[1] === ' ')) break;
      var colon = findColon(ln.text);
      if (colon === -1) { i++; continue; } // not a mapping line — tolerate
      var key = unquote(ln.text.slice(0, colon));
      var val = ln.text.slice(colon + 1).trim();
      if (val === '' ) {
        var j = i + 1;
        if (j < lines.length && lines[j].indent > base) {
          var r = parseBlock(lines, j, lines[j].indent, state);
          obj[key] = r[0]; i = r[1];
        } else if (j < lines.length && lines[j].indent === base &&
                   lines[j].text[0] === '-' && (lines[j].text.length === 1 || lines[j].text[1] === ' ')) {
          // sequence at the SAME indent as its key — legal YAML, common in workflows
          var r2 = parseSeq(lines, j, base, state);
          obj[key] = r2[0]; i = r2[1];
        } else { obj[key] = null; i++; }
      } else if (val === '|' || val === '>' || /^[|>][-+]?\d*$/.test(val)) {
        // block scalar — swallow the indented body as text
        var buf = [], k = i + 1;
        while (k < lines.length && lines[k].indent > base) { buf.push(lines[k].text); k++; }
        obj[key] = buf.join('\n'); i = k;
      } else {
        obj[key] = parseFlow(val); i++;
      }
    }
    return [obj, i];
  }

  function parse(text) {
    if (typeof text !== 'string') throw new Error('miniYAML.parse expects a string');
    var raw = text.replace(/\r\n?/g, '\n').split('\n');
    var lines = [];
    for (var i = 0; i < raw.length; i++) {
      if (/\t/.test(raw[i].match(/^[ \t]*/)[0])) {
        throw new Error('line ' + (i + 1) + ': tab used for indentation — YAML forbids tabs');
      }
      var code = stripComment(raw[i]);
      if (code.trim() === '' || code.trim() === '---') continue;
      lines.push({ indent: indentOf(code), text: code.trim(), lineNo: i + 1 });
    }
    if (!lines.length) return {};
    var res = parseBlock(lines, 0, lines[0].indent, {});
    return res[0];
  }

  return { parse: parse, _unquote: unquote, _parseFlow: parseFlow };
});
