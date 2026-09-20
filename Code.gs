/**
 * 事務事業優先度評価ツール 投票バックエンド（GAS+Sheets版）
 * Supabaseを使わない場合、投票の書き込み・読み取りをこのWebアプリ経由で行う。
 * このファイルは自治体名に依存しない汎用テンプレートなので、内容の変更は不要。
 *
 * 【セットアップ手順】詳細は スターターキット.md「独立運用のための読み替え」節を参照
 * 1. 新規Googleスプレッドシートを作成する
 * 2. シート名を「ratings」に変更し、1行目にヘッダーを入れる：
 *    id | municipality_id | event_no | rating | submitted_at
 * 3. 拡張機能 → Apps Script を開き、このファイルの内容を貼り付けて保存
 * 4. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」
 *    - 実行するユーザー：自分
 *    - アクセスできるユーザー：全員
 * 5. 発行されたウェブアプリのURLを、build_{自治体}_v3.py の
 *    GAS_URL = '...' に貼り付けて再ビルドする
 */

var SHEET_NAME = 'ratings';

function getSheet_() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
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

// 【注意】書き込みはdoPostではなくdoGet(action=insert)で行う。
// GAS Web Appは匿名アクセス時にscript.googleusercontent.comへ302リダイレクトする仕組みのため、
// ブラウザのfetch()でPOSTすると仕様上GETへ自動変換されボディが失われる（既知の制約）。
// GET→GETのリダイレクトならこの問題が起きないため、書き込みもGETのクエリパラメータで行う。
function doPost(e) {
  return jsonOut_({ ok: false, error: 'not supported: use GET with action=insert' });
}

// 書き込み（action=insert）／集計取得（action=agg）／生データ取得（action=raw）
function doGet(e) {
  try {
    var action = e.parameter.action;
    var municipalityId = e.parameter.municipality_id;

    if (action === 'insert') {
      var pairs = JSON.parse(e.parameter.rows || '[]'); // [[event_no, rating], ...]
      if (!pairs.length) return jsonOut_({ ok: false, error: 'no rows' });
      var inserted = insertRows_(municipalityId, pairs);
      return jsonOut_({ ok: true, inserted: inserted });
    }

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
    if (action === 'raw') {
      rows.sort(function (a, b) { return String(a.submitted_at).localeCompare(String(b.submitted_at)); });
      return jsonOut_({ ok: true, rows: rows });
    }
    return jsonOut_({ ok: false, error: 'unknown action' });
  } catch (err) {
    return jsonOut_({ ok: false, error: String(err) });
  }
}
