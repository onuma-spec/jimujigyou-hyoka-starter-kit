/**
 * 事務事業優先度評価ツール 投票・コメントバックエンド（GAS+Sheets版）
 * 投票・コメントの書き込み・読み取りをこのWebアプリ経由で行う。
 * このファイルは自治体名に依存しない汎用テンプレートなので、内容の変更は不要。
 *
 * 【セットアップ手順】詳細は スターターキット.md「独立運用のための読み替え」節を参照
 * 1. 新規Googleスプレッドシートを作成する
 * 2. 以下3枚のシートを作成し、それぞれ1行目にヘッダーを入れる：
 *    シート名「ratings」：         id | municipality_id | event_no | rating | submitted_at
 *    シート名「comments」：        id | municipality_id | event_no | comment | submitted_at
 *    シート名「comment_reports」： id | comment_id | municipality_id | reported_at
 * 3. 拡張機能 → Apps Script を開き、このファイルの内容を貼り付けて保存
 * 4. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」
 *    - 実行するユーザー：自分
 *    - アクセスできるユーザー：全員
 * 5. 発行されたウェブアプリのURLを、build_html.py の
 *    GAS_URL = '...' に貼り付けて再ビルドする
 *
 * ※ 投票機能とコメント機能は共通の LABELS.enable_voting で一括ON/OFFする設計（本体ツールと統一）。
 *    コメント機能だけ使わない場合は、上記のcomments・comment_reportsシート作成をスキップしてよい
 *    （build_html.pyのJS側でコメント関連のUIも一括で出ないようにする場合は別途相談すること）。
 */

var SHEET_NAME = 'ratings';
var COMMENTS_SHEET_NAME = 'comments';
var REPORTS_SHEET_NAME = 'comment_reports';
var REPORT_HIDE_THRESHOLD = 3; // 同一コメントへの通報がこの件数に達したら一覧から除外する
var COMMENT_MAX_LENGTH = 500;  // コメント本文の最大文字数

// クライアント側（評価カードのメモ欄）と同じ4パターン。
// サーバー側でも同じチェックを行う（クライアント側のみだと直接APIを叩かれた場合に素通りするため）。
var PII_PATTERNS = [
  /0\d{1,4}-\d{1,4}-\d{3,4}/,
  /[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}/,
  /https?:\/\/\S+/,
  /(私|僕|自分)の名前は|本名は/
];
function containsPii_(text) {
  for (var i = 0; i < PII_PATTERNS.length; i++) {
    if (PII_PATTERNS[i].test(text)) return true;
  }
  return false;
}

function getSheet_() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
}
function getCommentsSheet_() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(COMMENTS_SHEET_NAME);
}
function getReportsSheet_() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(REPORTS_SHEET_NAME);
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function insertRows_(municipalityId, pairs) {
  // pairs: [[event_no, rating], ...]
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = getSheet_();
    var lastRow = sheet.getLastRow(); // ヘッダー行を含む。データ0件ならlastRow=1
    var nextId = Math.max(lastRow - 1, 0);
    var now = new Date().toISOString();
    var values = pairs.map(function (p) {
      nextId++;
      return [nextId, municipalityId, p[0], p[1], now];
    });
    sheet.getRange(lastRow + 1, 1, values.length, 5).setValues(values);
    return values.length;
  } finally {
    lock.releaseLock();
  }
}

// コメント1件を挿入し、新しいidを返す
function insertComment_(municipalityId, eventNo, comment) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = getCommentsSheet_();
    var lastRow = sheet.getLastRow();
    var nextId = Math.max(lastRow - 1, 0) + 1;
    var now = new Date().toISOString();
    sheet.getRange(lastRow + 1, 1, 1, 5).setValues([[nextId, municipalityId, eventNo, comment, now]]);
    return nextId;
  } finally {
    lock.releaseLock();
  }
}

// 通報1件を挿入する
function insertReport_(commentId, municipalityId) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = getReportsSheet_();
    var lastRow = sheet.getLastRow();
    var nextId = Math.max(lastRow - 1, 0) + 1;
    var now = new Date().toISOString();
    sheet.getRange(lastRow + 1, 1, 1, 4).setValues([[nextId, commentId, municipalityId, now]]);
    return nextId;
  } finally {
    lock.releaseLock();
  }
}

// comment_id -> 通報件数 のマップを作る
function getReportCounts_() {
  var sheet = getReportsSheet_();
  var values = sheet.getDataRange().getValues();
  var counts = {};
  values.slice(1).forEach(function (row) {
    if (row[0] === '' || row[0] === null) return;
    var commentId = String(row[1]);
    counts[commentId] = (counts[commentId] || 0) + 1;
  });
  return counts;
}

// 【注意】書き込みはdoPostではなくdoGet(action=insert等)で行う。
// GAS Web Appは匿名アクセス時にscript.googleusercontent.comへ302リダイレクトする仕組みのため、
// ブラウザのfetch()でPOSTすると仕様上GETへ自動変換されボディが失われる（既知の制約）。
// GET→GETのリダイレクトならこの問題が起きないため、書き込みもGETのクエリパラメータで行う。
function doPost(e) {
  return jsonOut_({ ok: false, error: 'not supported: use GET' });
}

function doGet(e) {
  try {
    var action = e.parameter.action;
    var municipalityId = e.parameter.municipality_id;

    // ── 投票（ratings） ─────────────────────────────────────────────
    if (action === 'insert') {
      var pairs = JSON.parse(e.parameter.rows || '[]'); // [[event_no, rating], ...]
      if (!pairs.length) return jsonOut_({ ok: false, error: 'no rows' });
      var inserted = insertRows_(municipalityId, pairs);
      return jsonOut_({ ok: true, inserted: inserted });
    }
    if (action === 'agg' || action === 'raw') {
      var sheet = getSheet_();
      var values = sheet.getDataRange().getValues(); // 1行目はヘッダー
      var rows = values.slice(1)
        .filter(function (row) { return row[0] !== '' && row[0] !== null; })
        .map(function (row) {
          return {
            id: row[0],
            municipality_id: row[1],
            event_no: String(row[2]),
            rating: row[3],
            submitted_at: row[4] instanceof Date ? row[4].toISOString() : row[4]
          };
        })
        .filter(function (r) { return !municipalityId || r.municipality_id === municipalityId; });

      if (action === 'agg') {
        var agg = {};
        rows.forEach(function (r) {
          if (!agg[r.event_no]) agg[r.event_no] = { '続行': 0, '廃止': 0, '見直し': 0 };
          if (agg[r.event_no][r.rating] !== undefined) agg[r.event_no][r.rating]++;
        });
        return jsonOut_({ ok: true, agg: agg });
      }
      // action === 'raw'
      rows.sort(function (a, b) { return String(a.submitted_at).localeCompare(String(b.submitted_at)); });
      return jsonOut_({ ok: true, rows: rows });
    }

    // ── コメント機能（comments / comment_reports） ─────────────────────
    if (action === 'comment_insert') {
      var eventNo = e.parameter.event_no;
      var comment = (e.parameter.comment || '').toString();
      if (!eventNo) return jsonOut_({ ok: false, error: 'missing event_no' });
      if (!comment.trim()) return jsonOut_({ ok: false, error: 'empty comment' });
      if (comment.length > COMMENT_MAX_LENGTH) return jsonOut_({ ok: false, error: 'comment too long' });
      if (containsPii_(comment)) return jsonOut_({ ok: false, error: 'pii detected' });
      var newId = insertComment_(municipalityId, eventNo, comment);
      return jsonOut_({ ok: true, id: newId });
    }

    if (action === 'comment_report') {
      var commentId = e.parameter.comment_id;
      if (!commentId) return jsonOut_({ ok: false, error: 'missing comment_id' });
      insertReport_(commentId, municipalityId);
      return jsonOut_({ ok: true });
    }

    if (action === 'comment_list') {
      var csheet = getCommentsSheet_();
      var cvalues = csheet.getDataRange().getValues();
      var reportCounts = getReportCounts_();
      var crows = cvalues.slice(1)
        .filter(function (row) { return row[0] !== '' && row[0] !== null; })
        .map(function (row) {
          return {
            id: row[0],
            municipality_id: row[1],
            event_no: String(row[2]),
            comment: row[3],
            submitted_at: row[4] instanceof Date ? row[4].toISOString() : row[4]
          };
        })
        .filter(function (r) { return !municipalityId || r.municipality_id === municipalityId; })
        .filter(function (r) { return (reportCounts[String(r.id)] || 0) < REPORT_HIDE_THRESHOLD; });
      crows.sort(function (a, b) { return String(a.submitted_at).localeCompare(String(b.submitted_at)); });
      return jsonOut_({ ok: true, comments: crows });
    }

    return jsonOut_({ ok: false, error: 'unknown action' });
  } catch (err) {
    return jsonOut_({ ok: false, error: String(err) });
  }
}
