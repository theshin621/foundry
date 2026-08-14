/* lib/pwcsv-remap.js — password-CSV format detection + remapping to Bitwarden CSV.
 *
 * The reusable piece from ship 015. Depends on lib/csv-parse.vendor.js (Papa Parse)
 * being loaded first; this file deliberately contains NO tokenising of its own.
 *
 * SCOPE IS CLOSED BY CONSTRUCTION AND THAT IS THE DESIGN, not a limitation to be
 * fixed later. BOTTLENECKS #1's diagnosis is that long-tailed scope lets each fix
 * cycle reveal the next rule, so ships 006/007/012 ground and died. Exactly four
 * source formats are supported. Everything else is REFUSED BY NAME. A refusal is a
 * correct output. If a checker finds a fifth format mishandled, the answer is a
 * better refusal message -- never a fifth parser.
 *
 * The column mappings below are not invented. They are transcribed from pass_import's
 * manager classes (ChromeCSV, BitwardenCSV, LastpassCSV, OnePassword8CSV), which is
 * also what oracles/015-password-csv-remapper/oracle.py computes ground truth with.
 * If these two ever disagree, the oracle wins and this file is wrong.
 */
(function (root) {
  'use strict';

  // src key -> canonical key. Canonical keys match pass_import's normalised names.
  var FORMATS = {
    chrome: {
      label: 'Chrome / Chromium / Edge',
      // `note` is the distinguisher against LastPass, which is otherwise identical.
      needs: ['name', 'url', 'username', 'password'],
      forbids: ['extra', 'grouping', 'login_password'],
      map: { name: 'title', username: 'login', password: 'password', url: 'url', note: 'comments' }
    },
    bitwarden: {
      label: 'Bitwarden',
      needs: ['name', 'login_username', 'login_password'],
      forbids: [],
      map: {
        name: 'title', login_username: 'login', login_password: 'password',
        login_uri: 'url', notes: 'comments', folder: 'group', login_totp: 'otpauth'
      }
    },
    lastpass: {
      label: 'LastPass',
      // `extra` is LastPass's notes column; `grouping` its folder column.
      needs: ['name', 'username', 'password', 'extra'],
      forbids: ['login_password'],
      map: {
        name: 'title', username: 'login', password: 'password', url: 'url',
        extra: 'comments', grouping: 'group'
      }
    },
    onepassword: {
      label: '1Password 8',
      // Case-SENSITIVE, and `Url` (not `URL`) is what separates this from KeePass,
      // which also capitalises Title/Username/Password and must be refused.
      needs: ['Title', 'Username', 'Password', 'Url'],
      forbids: ['Group', 'URL'],
      map: {
        Title: 'title', Username: 'login', Password: 'password', Url: 'url',
        Notes: 'comments', OTPAuth: 'otpauth', Tags: 'group'
      }
    }
  };

  // Bitwarden's own import columns, in Bitwarden's own order.
  var OUT_COLS = ['folder', 'favorite', 'type', 'name', 'notes', 'fields',
                  'login_uri', 'login_username', 'login_password', 'login_totp'];
  var OUT_FROM_CANON = {
    group: 'folder', title: 'name', comments: 'notes', url: 'login_uri',
    login: 'login_username', password: 'login_password', otpauth: 'login_totp'
  };

  function detect(headers) {
    var present = {};
    for (var i = 0; i < headers.length; i++) present[headers[i]] = true;
    var hits = [];
    for (var id in FORMATS) {
      if (!Object.prototype.hasOwnProperty.call(FORMATS, id)) continue;
      var f = FORMATS[id], ok = true, j;
      for (j = 0; j < f.needs.length; j++) if (!present[f.needs[j]]) { ok = false; break; }
      if (ok) for (j = 0; j < f.forbids.length; j++) if (present[f.forbids[j]]) { ok = false; break; }
      if (ok) hits.push(id);
    }
    // Ambiguity is a refusal, not a coin flip. Guessing a mapping wrong on a password
    // file is the worst outcome this tool can produce, so it declines instead.
    return hits.length === 1 ? hits[0] : null;
  }

  /* remap(text) -> {state, format, count, csv, reason}
   *   state: 'ok' | 'empty' | 'refused'   (mirrors the oracle's interface contract) */
  function remap(text) {
    if (typeof text !== 'string' || text.replace(/\s+/g, '') === '') {
      return refuse('the file is empty');
    }
    // Papa handles BOM, CRLF, quoted delimiters, escaped quotes and embedded newlines.
    var res = root.Papa.parse(text, { header: true, skipEmptyLines: 'greedy' });
    var headers = (res.meta && res.meta.fields) || [];
    if (!headers.length) return refuse('no CSV header row was found');

    var fmt = detect(headers);
    if (!fmt) {
      return refuse('these columns do not match any supported export (' +
                    headers.slice(0, 8).join(', ') + ')');
    }

    var map = FORMATS[fmt].map, rows = res.data || [], out = [], n = 0;
    for (var i = 0; i < rows.length; i++) {
      var src = rows[i], canon = {}, any = false, k;
      for (k in map) {
        if (!Object.prototype.hasOwnProperty.call(map, k)) continue;
        var v = src[k];
        // Preserve verbatim. No trimming: "  spaces  " is a real password.
        if (v !== undefined && v !== null && v !== '') { canon[map[k]] = String(v); any = true; }
      }
      // A row is real if ANY mapped field carried data. An empty password is a real
      // row, not a skip -- dropping it silently loses a credential.
      if (!any) continue;
      var rec = {};
      for (var c = 0; c < OUT_COLS.length; c++) rec[OUT_COLS[c]] = '';
      rec.type = 'login';
      for (k in canon) {
        if (Object.prototype.hasOwnProperty.call(canon, k) && OUT_FROM_CANON[k]) {
          rec[OUT_FROM_CANON[k]] = canon[k];
        }
      }
      out.push(rec);
      n++;
    }

    if (!n) return { state: 'empty', format: fmt, count: 0, csv: '', reason: 'no entries found' };
    // unparse, not string concatenation: the borrowed primitive works both ways.
    return {
      state: 'ok', format: fmt, count: n,
      csv: root.Papa.unparse({ fields: OUT_COLS, data: out }), reason: ''
    };
  }

  function refuse(reason) {
    return { state: 'refused', format: '', count: 0, csv: '', reason: reason };
  }

  root.PWCSV = { FORMATS: FORMATS, OUT_COLS: OUT_COLS, detect: detect, remap: remap };
})(typeof window !== 'undefined' ? window : this);
