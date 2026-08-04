r"""
build_html.py（旧build_kitamoto_v3.py。自治体固有のビルドテンプレート本体）
北本市 事務事業優先度評価ツール HTML生成スクリプト（v3試作・全体像マップ設計）
03_パッチ済みデータ\\kitamoto_master_v2.csv → 04_本番HTML生成\\kitamoto_v3_index.html

build_kitamoto_v2.py をベースに、UXを3画面（①全体像マップ ②個別評価opt-in ③サマリー・投票）へ再構成。
既存の kitamoto_index.html（v2・公開中）はそのまま維持し、本スクリプトは上書きしない。

── データパイプライン（①元データ→②抽出→③パッチ→④本スクリプト）─────────────────
① 元データ：01_元データ\R6kitamoto_itiran.xlsx（Excel・451件基本情報）＋ 01_元データ\R6kitamoto_sheet.pdf（902ページ）
② 抽出　：02_抽出スクリプト\extract_kitamoto_v2.py → 03_パッチ済みデータ\kitamoto_master_v2.csv
③ パッチ：03_パッチ済みデータ\gen_story_kitamoto.py（story_p1/p2をAI生成しCSVへ直接書き込み）
　　　　　※②を再実行（再抽出）した場合、story_p1/p2が消えるので必ず③を再実行すること
④ 本スクリプト：kitamoto_master_v2.csv・classified2_all.json・kitamoto_revised.json を読み込みHTML生成
"""
import csv, json, os

BASE = r"C:\Users\onuma\Desktop\AIの作業場\小さな政府\07_事務事業評価"
OUT_DIR = os.path.join(BASE, "04_本番HTML生成")

# ── 支援対象×提供形態 13分類（AI分類パイロット結果＋G48件の個別レビュー＋分類ルール改良の補正）─────
# classified2_all.json の分類そのもの（旧コード）は変更せず、表示用のコードだけ新体系（1〜13）に変換する。
# 新コードの並び：大枠は4階層（1-5個人向け／6-8団体・地域・合議体向け／9-10内部向け／11-12広報・不明）＋13（複合・主従なし）。
# 個人向け(1-5)は「経由の度合い」順（現金→引換券→業者経由モノ→業者経由サービス→市直営サービス。表示ラベルは1/2/3を統合）、
# それ以外は各グループ内の予算規模が大きい順、Gは常に12として最後、13は「主たる提供形態を特定できない複合事業」用の新設分類。
OLD_TO_NEW_PTYPE = {
    '1': '1', '2': '2', '3': '3', '4': '4',
    'A': '6', 'D': '7', 'C': '8',
    'B': '9', 'E2': '10',
    'E1': '11', 'G': '12',
}
# G48件の個別レビューで判明した誤分類・新設12分類（5：住民へ直接サービスを提供）該当の手動補正（事業番号→新コード）
PTYPE_MANUAL_OVERRIDE = {
    '779': '4',  # 大学公開講座開催事業：業者（大学）経由でサービス提供
    '781': '4',  # 子ども大学講座開催事業：同上
    '855': '5',  # 市役所出前講座事業：市職員が直接講師派遣
    '787': '5',  # きたもとピアノフェスティバル実施事業：市が直接演奏機会を提供
    '827': '5',  # 体力測定会実施事業：市が直接測定・結果提供
    '849': '5',  # 北本さくらウォーク事業：市が直接イベント運営
    '831': '5',  # スポーツ推進委員事業：推進委員が直接実技指導
}
# 分類ルール改良（1/2/3ラベル統合・7の対象拡大・13新設）に伴う候補63件の再判定結果を追加でマージ。
# kitamoto_revised.json は「機械的フィルタ（丸数字2個以上 or 現ptype=12）」で絞った63件をoverviewベースで再判定した結果。
# 上記7件（既存の個別レビュー分）と事業番号が重複するケースは無い前提だが、念のため再判定結果を優先する。
with open(f"{OUT_DIR}\\kitamoto_revised.json", encoding='utf-8') as f:
    PTYPE_MANUAL_OVERRIDE.update({r['no']: r['new_ptype'] for r in json.load(f)})
with open(f"{OUT_DIR}\\classified2_all.json", encoding='utf-8') as f:
    PTYPE_BY_NO = {
        r['no']: PTYPE_MANUAL_OVERRIDE.get(r['no'], OLD_TO_NEW_PTYPE.get(r['type'], '12'))
        for r in json.load(f)
    }

# ── EVENTS（v2と同じマッピング＋ptype追加）─────────────────────────────────
events = []
with open(f"{BASE}\\03_パッチ済みデータ\\kitamoto_master_v2.csv", encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        dept = row['dept'] or ''
        bureau = row['bureau'] or ''
        dept_display = f"{bureau}　{dept}" if bureau and dept else (dept or bureau)
        events.append({
            'no':           row['no'],
            'name':         row['name'],
            'bureau':       bureau or 'データなし',
            'dept':         dept_display or 'データなし',
            'budget':       int(row['budget'] or 0),
            'root':         row['root'] or 'データなし',
            'ev':           row['ev'] or '',
            'ptype':        PTYPE_BY_NO.get(row['no'], '12'),
            'story_p1':     row['story_p1'] or '',
            'story_p2':     row['story_p2'] or '',
            'story_impact': row['story_impact'] or '',
            'pdf_page':     int(row['pdf_page'] or 0),
            'cls':          row['cls'] or 'データなし',
        })

events.sort(key=lambda e: e['pdf_page'])
DATA_JSON = json.dumps(events, ensure_ascii=False, separators=(',', ':'))

# ── LABELS（v2と共通、v3試作用にキーのみ変更）──────────────────────────────
LABELS = {
    'bureau':            'データなし',
    'dept':              '担当課',
    'cls':               '施策',
    'budget_col':        'R6決算(千円)',
    'no_col':            'ページ番号',
    'tool_title':        '北本市 事務事業優先度評価ツール',
    'card_title':        '北本市 令和6年度 事務事業評価',
    'summary_title':     '北本市 令和6年度 事務事業優先度評価結果',
    'output_file':       'kitamoto_v3_index.html',
    'csv_filename':      '北本市_令和6年度_事務事業優先度評価結果.csv',
    'source_url':        'https://www.city.kitamoto.lg.jp/soshiki/seisakusuisinbu/seisakusuisin/gyomu/hyouka/r6jimujigyouhyouka/18439.html',
    'population':        65274,
    'local_storage_key': 'kitamoto6_v3_ratings',
    'pdf_url':           'https://www.city.kitamoto.lg.jp/material/files/group/52/R6jimujigyouhyoukasi-to.pdf',
    'personnel_cost':    '含む',   # 固定3択に当てはめず実態を記述する自由記述（fixed_prompt.md参照）
    # カードのセクション表示可否（データの有無ではなく制作者の好みで決めてよい。fixed_prompt.md参照）
    'show_emeta':        True,   # 事業番号・担当課
    'show_tags':         True,   # タグ行（法定根拠／行政評価／提供形態）
    'show_desc':         True,   # 目的・事業内容
    'show_budget':       True,   # 決算額・人件費チェック（セット）
    'show_outcome':      True,   # 成果
    'show_impact':       True,   # 廃止した場合の影響
}
LABELS_JSON = json.dumps(LABELS, ensure_ascii=False)

# ── CSS ─────────────────────────────────────────────────────────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Hiragino Sans','Noto Sans JP',sans-serif;background:#f3f4f6;color:#1f2937;min-height:100vh}
#app{max-width:780px;margin:0 auto;padding:12px}

.hd{background:#1e40af;color:#fff;padding:14px 16px;border-radius:8px;margin-bottom:12px}
.hd h1{font-size:1.1rem;font-weight:700}
.hd .sub{font-size:.8rem;opacity:.8;margin-top:3px}
.card-nav{display:flex;justify-content:space-between;align-items:center;gap:6px}
.cnav-btn{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.4);color:#fff;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:1;min-width:0;max-width:42%}
.cnav-btn:hover{background:rgba(255,255,255,.25)}
.cnav-mid{font-size:.85rem;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center;padding:0 4px}
.cnav-mid-wrap{font-size:.85rem;flex:1;min-width:0;text-align:center;padding:0 4px;line-height:1.4}

.card{background:#fff;border-radius:8px;padding:16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.1)}

.btn{padding:9px 18px;border:none;border-radius:6px;cursor:pointer;font-size:.9rem;font-weight:600;transition:opacity .15s}
.btn:hover{opacity:.85}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-p{background:#1e40af;color:#fff}
.btn-k{background:#22c55e;color:#fff}
.btn-h{background:#ef4444;color:#fff}
.btn-f{background:#f59e0b;color:#fff}
.btn-o{background:#fff;border:1px solid #d1d5db;color:#374151}
.btn-sm{padding:6px 12px;font-size:.8rem}
.btn-full{width:100%;margin-bottom:8px}

.bbtns{display:flex;gap:8px;flex-wrap:wrap}

/* マップ画面 */
.filterrow{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.stbtn{padding:7px 14px;border:1px solid #d1d5db;border-radius:20px;background:#fff;color:#374151;font-size:.82rem;font-weight:600;cursor:pointer}
.stbtn.active{background:#1e40af;color:#fff;border-color:#1e40af}
.maphint{font-size:.82rem;color:#6b7280;line-height:1.6}
.fresult{font-size:.95rem;font-weight:600;color:#1e40af;margin-bottom:8px}
.sec-heading{font-size:.85rem;font-weight:700;color:#374151;margin-bottom:6px}

.clsgrid-wrap{border:1px solid #eef0f2;border-radius:6px;padding:8px;max-height:35vh;overflow-y:auto}
.clsgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:6px}
.clsbox{background:#fff;border:1px solid #eef0f2;border-radius:6px;padding:7px 10px;cursor:pointer;transition:background .15s;min-width:0}
.clsbox:hover{background:#f7f9fc}
.clstop{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:4px}
.clsname{font-weight:700;font-size:.85rem;color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.clsamt{font-size:.76rem;color:#374151;white-space:nowrap;flex-shrink:0}
.clsamt b{color:#1e40af}
.clsbar-wrap{background:#eef2f7;border-radius:3px;height:5px;margin-bottom:4px;overflow:hidden}
.clsbar{background:#1e40af;height:100%;border-radius:3px}
.clsmeta{font-size:.7rem;color:#9ca3af}

/* cls drilldown：行政評価（ev）でグルーピング。事業一覧は表形式（法定義務・提供形態を列見出しで明示） */
.evsec{border:1px solid #eef0f2;border-radius:6px;margin-bottom:8px;overflow:hidden}
.evsec:last-child{margin-bottom:0}
.evsec summary{padding:9px 12px;cursor:pointer;font-weight:700;font-size:.85rem;color:#374151;background:#f8f9fb;list-style:none;user-select:none}
.evsec summary::-webkit-details-marker{display:none}
.evsec summary::before{content:'▶ ';font-size:.7rem;color:#9ca3af}
.evsec[open] summary::before{content:'▼ '}
.evsec-body{padding:6px 12px 2px}
.evtbl-wrap{overflow:auto;max-height:320px;border:1px solid #eef0f2;border-radius:6px}
.evtbl{border-collapse:collapse;font-size:.82rem}
.evtbl th{text-align:left;font-weight:600;color:#6b7280;font-size:.7rem;padding:4px 8px;border-bottom:1px solid #e5e7eb;white-space:nowrap;position:sticky;top:0;background:#fff;z-index:1}
.evtbl td{padding:8px;border-bottom:1px solid #f3f4f6;vertical-align:middle;white-space:normal;word-break:break-word}
.evtbl tr:last-child td{border-bottom:none}
.evtd-chk{width:32px;min-width:32px;max-width:32px}
.evtd-chk input{width:16px;height:16px}
.evtd-name{font-weight:600;color:#111827;cursor:pointer;width:126px;min-width:126px;max-width:126px}
.evtd-budget{color:#374151;width:65px;min-width:65px;max-width:65px}
.evtd-root{width:70px;min-width:70px;max-width:70px;font-size:.7rem;font-weight:600;overflow:hidden}
.evtd-ptype{width:100px;min-width:100px;max-width:100px;font-weight:600}
.evtd-mine{width:80px;min-width:80px;max-width:80px}
.evtd-vote{width:70px;min-width:70px;max-width:70px}
.evtbl td.evtd-budget{white-space:nowrap}
.evtbl th.evtd-root{white-space:normal}
.vote-stack{display:flex;flex-direction:column;gap:2px;align-items:flex-start}

/* サマリー画面：評価結果一覧（ブラウザ表示用の圧縮テーブル。列を減らしセル内で折り返す） */
.votetbl-wrap{overflow:auto;max-height:420px;border:1px solid #eef0f2;border-radius:6px}
.votetbl{width:100%;border-collapse:collapse;font-size:.82rem}
.votetbl th{text-align:left;font-weight:600;color:#6b7280;font-size:.7rem;padding:6px 8px;border-bottom:1px solid #e5e7eb;position:sticky;top:0;background:#fff;z-index:1}
.votetbl td{padding:8px;border-bottom:1px solid #f3f4f6;vertical-align:top;white-space:normal}
.votetbl tr:last-child td{border-bottom:none}
.votetbl .vsub{font-size:.72rem;color:#6b7280;margin-top:2px}
.votetbl .vno{font-size:.7rem;color:#9ca3af}
.vtag-stack{display:flex;flex-direction:column;gap:3px;align-items:flex-start}

/* サマリー画面：印刷専用の完全版（10列）テーブル。画面には出さず@media printでのみ表示 */
.votetbl-print{display:none}

/* タグ */
.tags{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:600}
.troot-法定義務あり{background:#dbeafe;color:#1d4ed8}
.troot-法定義務なし{background:#fef3c7;color:#92400e}
.troot-判断できない{background:#f3f4f6;color:#6b7280}
.troot-データなし{background:#f3f4f6;color:#9ca3af}
.tev-拡大{background:#dcfce7;color:#15803d}
.tev-現状継続{background:#dbeafe;color:#1d4ed8}
.tev-改善（手段変更）{background:#fef3c7;color:#92400e}
.tev-縮小{background:#ffedd5;color:#c2410c}
.tev-廃止方向{background:#fee2e2;color:#dc2626}
.tev-完了{background:#f3e8ff;color:#7c3aed}
.tev-続行{background:#dcfce7;color:#15803d}
.tev-廃止{background:#fee2e2;color:#dc2626}
.tev-見直し{background:#fef3c7;color:#92400e}
.tptype-green{background:#ccfbf1;color:#0f766e}
.tptype-blue{background:#dbeafe;color:#1d4ed8}
.tptype-gray{background:#f3f4f6;color:#6b7280}
.tptype-amber{background:#fef3c7;color:#92400e}
.tptype-purple{background:#ede9fe;color:#6d28d9}
/* カードの説明：処理タイプバッジ（既存タグと同系色を再利用） */
.tproc-転記{background:#f3f4f6;color:#6b7280}
.tproc-区分・分類{background:#dbeafe;color:#1d4ed8}
.tproc-AI分類{background:#ede9fe;color:#6d28d9}
.tproc-AI要約{background:#ede9fe;color:#6d28d9}
.tproc-固定表示{background:#fef3c7;color:#92400e}
/* カードの説明：評価シート起点の対応表（画面幅によらず縦積みブロックに統一） */
.gintro{font-size:.84rem;line-height:1.8;color:#6b7280;margin-bottom:16px}
.gproc-legend{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px;font-size:.78rem}
.gproc-legend span{display:flex;align-items:center;gap:5px}
.gtbl{width:100%;margin-bottom:16px;font-size:.82rem;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden}
.grow{display:flex;flex-wrap:wrap;gap:2px 10px;align-items:baseline;border-top:1px solid #e5e7eb;padding:10px 12px}
.grow:first-child{border-top:none}
.grow.ghead{display:none}
.gc-item{font-weight:700;color:#1e40af;flex:none;order:1}
.gc-proc{flex:none;margin-left:auto;order:2}
.gc-src{flex:0 0 100%;max-width:640px;color:#374151;line-height:1.8;margin-top:2px;order:3}
.gmap{margin-top:6px}
.gmap .row{display:flex;gap:6px;padding:3px 0;border-top:1px dashed #eef0f2;font-size:.78rem}
.gmap .row:first-child{border-top:none;padding-top:6px}
.gmap .k{color:#6b7280;flex:1;min-width:0}
.gmap .v{color:#1e40af;font-weight:600;flex:none;white-space:nowrap;padding-left:6px}
/* 評価ボタンの説明（表以外の単独セクション） */
.gitem{margin-top:4px}
.glbl{font-weight:700;font-size:.92rem;margin-bottom:6px;color:#1e40af}
.gitem p{font-size:.85rem;line-height:1.8;color:#374151;margin:0}
/* ドリルダウン表の提供形態列：タグではなくフル文言のプレーンテキスト表示（色分けのみ引き継ぐ） */
.ptype-plain-green{color:#0f766e}
.ptype-plain-blue{color:#1d4ed8}
.ptype-plain-gray{color:#6b7280}
.ptype-plain-amber{color:#92400e}
.ptype-plain-purple{color:#6d28d9}
/* ドリルダウン表の法定義務列：列幅確保のためタグではなくプレーンテキスト表示 */
.root-plain-法定義務あり{color:#1d4ed8}
.root-plain-法定義務なし{color:#92400e}
.root-plain-判断できない{color:#6b7280}
.root-plain-データなし{color:#9ca3af}

/* 評価カード（opt-inキュー） */
.pbwrap{background:#e5e7eb;border-radius:4px;height:6px;margin-bottom:12px}
.pbfill{background:#1e40af;height:100%;border-radius:4px;transition:width .3s}
.ecard{background:#fff;border-radius:8px;padding:18px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.1);border-left:4px solid #e5e7eb}
.ecard.rk{border-left-color:#22c55e}
.ecard.rh{border-left-color:#ef4444}
.ecard.rf{border-left-color:#f59e0b}
.emeta{font-size:.8rem;color:#6b7280;margin-bottom:6px}
.ename{font-size:1.15rem;font-weight:700;color:#111827;margin-bottom:4px;line-height:1.3}
.ebudget{font-size:.85rem;margin-bottom:12px;color:#374151}
.ebudget .amt{font-weight:700;font-size:1rem;color:#1e40af}
.story{margin-bottom:14px}
.story p{font-size:.9rem;line-height:1.75;color:#1f2937;margin-bottom:6px}
.story-label{font-size:.72rem;font-weight:700;color:#6b7280;margin-bottom:3px;letter-spacing:.03em}
.ai-note{font-size:.75rem;color:#713f12;line-height:1.65;margin-bottom:8px;background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:8px 10px}
.sticky-actions{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:2px solid #e5e7eb;z-index:100;box-shadow:0 -4px 12px rgba(0,0,0,.08)}
.sticky-inner{max-width:780px;margin:0 auto;padding:10px 12px}
.sticky-spacer{height:110px}
.sticky-spacer.tall{height:230px}
.rbtns{display:flex;gap:10px;margin:16px 0}
.rbtn{flex:1;padding:12px 6px;border:2px solid #e5e7eb;border-radius:8px;cursor:pointer;font-size:.9rem;font-weight:700;background:#f9fafb;color:#374151;text-align:center;transition:all .15s;line-height:1.4}
.rbtn:hover{border-color:#9ca3af}
.rbtn small{display:block;font-size:.7rem;font-weight:400;margin-top:2px;opacity:.8}
.rbtn.ak{background:#22c55e;color:#fff;border-color:#22c55e}
.rbtn.ah{background:#ef4444;color:#fff;border-color:#ef4444}
.rbtn.af{background:#f59e0b;color:#fff;border-color:#f59e0b}
.nav{display:flex;justify-content:space-between;align-items:center}
.cpos{font-size:.85rem;color:#6b7280}

/* サマリー */
.kgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
.kbox{background:#fff;border-radius:8px;padding:14px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.kbox .klbl{font-size:.75rem;color:#6b7280;margin-bottom:6px}
.kbox .knum{font-size:1.7rem;font-weight:700}
.kh .knum{color:#dc2626}
.kf .knum{color:#d97706}
.kk .knum{color:#059669}
.ku .knum{color:#6b7280}

.stbl{width:100%;border-collapse:collapse;font-size:.82rem}
.stbl th{background:#f3f4f6;padding:8px 10px;text-align:left;font-weight:600;border-bottom:1px solid #e5e7eb}
.stbl td{padding:7px 10px;border-bottom:1px solid #f3f4f6;vertical-align:top}
.stbl tr:last-child td{border-bottom:none}
.stbl-wrap{overflow-x:auto}

.pc{display:inline-block;padding:1px 6px;border-radius:4px;font-size:.75rem;font-weight:600;margin-right:2px;white-space:nowrap}
.pc-k{background:#dcfce7;color:#16a34a}
.pc-h{background:#fee2e2;color:#dc2626}
.pc-f{background:#fef3c7;color:#d97706}

@media(max-width:480px){
  .kgrid{grid-template-columns:repeat(2,1fr)}
  .rbtns{flex-direction:column}
}

@media print{
  .no-print{display:none !important}
  body{background:#fff}
  .card{box-shadow:none;border:1px solid #e5e7eb}
  .votetbl-wrap{display:none}
  .votetbl-print{display:block}
  .evtbl-wrap{max-height:none;overflow:visible;border:none}
  .evtbl td, .evtbl th{white-space:normal}
  @page{size:landscape}
}
"""

# ── JavaScript ───────────────────────────────────────────────────────────
JS = r"""
const EVENTS = """ + DATA_JSON + r""";
const LABELS = """ + LABELS_JSON + r""";
const LS_KEY = LABELS.local_storage_key;
const OLD_LS_KEY = 'kitamoto6_ratings'; // 旧v2版の保存キー（リニューアル案内の判定用）
const SUPABASE_URL = 'https://unkhamvtfathmoxmikmp.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_UArsQ1bcdira6J91O8kXjA_nGJ6MGtz';
const MUNICIPALITY_ID = 'kitamoto_r6'; // v2と同一ID（本番昇格・投票履歴を引き継ぐため）
const SUBMITTED_KEY = MUNICIPALITY_ID + '_submitted';
const sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

const ROOT_ORDER = ['法定義務あり','法定義務なし','判断できない','データなし'];
const EV_PRIORITY = ['拡大','現状継続','改善（手段変更）','縮小','廃止方向','完了']; // ドリルダウンのグループ表示順（歳出削減につなげるため拡大→縮小→廃止の順）

// 支援対象×提供形態 13分類（AI分類パイロット結果＋個別レビュー補正を row.ptype として反映。コードは1〜13に統一）
// 並び：1-5個人向け（経由の度合い順・1/2/3は表示ラベル統合）／6-8団体・地域・合議体向け（予算規模順）／9-10内部向け（予算規模順）／11-12広報・不明（Gは常に最後）／13は主従なしの複合形態
const PTYPE_LABEL = {
  '1': '住民へ現金・引換券・モノを支給', '2': '住民へ現金・引換券・モノを支給', '3': '住民へ現金・引換券・モノを支給',
  '4': '業者経由でサービスを提供',
  '5': '住民へ直接サービスを提供',
  '6': '施設・インフラを整備する',
  '7': '団体・事業者へ補助金を支給',
  '8': '会議体を運営する',
  '9': '内部の事務を処理する',
  '10': '調査・計画を実施する',
  '11': '住民へ情報を発信する',
  '12': '情報不足で分類できない',
  '13': '複数の提供形態が混在',
};
// ドリルダウン表用の短縮ラベル（列幅が狭いため）。個別評価画面等は引き続きPTYPE_LABEL（フル文言）を使用
const PTYPE_LABEL_SHORT = {
  '1': '給付', '2': '給付', '3': '給付',
  '4': '委託提供',
  '5': '直接提供',
  '6': 'ｲﾝﾌﾗ整備',
  '7': '補助金',
  '8': '会議運営',
  '9': '内部事務',
  '10': '調査計画',
  '11': '情報発信',
  '12': '分類不能',
  '13': '形態混在',
};
// タグの配色を4階層（誰を支援しているか）に束ねる。グルーピングには使わず、バッジの色分けのみに使用
const PTYPE_TIER = {
  '1': 'green', '2': 'green', '3': 'green', '4': 'green', '5': 'green',
  '6': 'blue', '7': 'blue', '8': 'blue',
  '9': 'gray', '10': 'gray',
  '11': 'amber', '12': 'amber',
  '13': 'purple',
};
let ratings = {};
let rootFilter = '';      // '' = 全事業 / ROOT_ORDERのいずれかで絞り込み（チャート・施策一覧・ドリルダウン全てに反映）
let curCls = null;        // 現在ドリルダウン中の施策
let selected = new Set(); // opt-in選択された事業番号
let queue = [];           // 評価キュー（selectedから作る）
let qCursor = 0;
let openEvKeys = null;    // ドリルダウンの行政評価セクションの開閉状態（チェックボックス操作の再描画をまたいで保持。nullなら次回描画時に既定値で初期化）
let peopleAgg = null;     // Supabase集計結果 {no: {続行,廃止,見直し}}（取得前はnull）
let voteFilter = '';      // 評価結果一覧のフィルタ：'' 全事業 / '続行'/'廃止'/'見直し' / '未評価'（自分は未評価・みんなは投票済み）
let curScreen = 'map';    // 現在表示中の画面（loadPeopleData完了後の再描画先を追跡）

function load() {
  try { ratings = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch(e) {}
  showRenewalNoticeIfNeeded();
  render('map');
  loadPeopleData(); // ドリルダウンで「みんなの評価」を見せるため、投票前でも起動時に取得する
}

// 旧v2利用者向け：評価内容が引き継がれないことの一度きりの案内（v2の保存キーが残っている＝過去に利用した形跡がある場合のみ表示）
function showRenewalNoticeIfNeeded() {
  const NOTICE_KEY = LS_KEY + '_renewal_notice_shown';
  if (localStorage.getItem(OLD_LS_KEY) && !localStorage.getItem(NOTICE_KEY)) {
    alert('このツールは新しくなりました。恐れ入りますが、以前ご利用いただいた際の評価内容は引き継がれません。お手数をおかけしますが、改めてご覧いただければと思います。');
    localStorage.setItem(NOTICE_KEY, '1');
  }
}

function fmt(n) {
  if (!n) return '0';
  return n.toLocaleString();
}
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function fracPct(count, total) {
  const pct = total ? Math.round(count / total * 100) : 0;
  return `${count}/${total}（${pct}%）`;
}

function personnelCostHtml() {
  // personnel_cost は固定3択（含む/含まない/確認取れず）ではなく、評価シートを確認した実態を
  // そのまま記述する自由記述（fixed_prompt.md参照）。単純に「含む」「含まない」で言い切れる
  // 自治体はそのまま書いてよいし、部分的にしか判定できない自治体は実態を明示する。
  return esc(LABELS.personnel_cost || '確認取れず');
}

function rootTagHtml(root) {
  return `<span class="tag troot-${esc(root)}">${esc(root)}</span>`;
}
function evTagHtml(ev) {
  return `<span class="tag tev-${esc(ev)}">行政評価：${esc(ev)}</span>`;
}
// 表の列見出し（法定義務／行政評価）で文脈が既に示されている場合の短縮版タグ
function rootTagShortHtml(root) {
  const short = root.startsWith('法定義務') ? root.replace('法定義務', '') : root;
  return `<span class="tag troot-${esc(root)}">${esc(short)}</span>`;
}
function evTagShortHtml(ev) {
  return `<span class="tag tev-${esc(ev)}">${esc(ev)}</span>`;
}
// ドリルダウン表用：法定義務をタグではなくプレーンテキストで表示（列幅確保のため2文字程度に折り返す）
function rootPlainHtml(root) {
  const short = root.startsWith('法定義務') ? root.replace('法定義務', '') : root;
  return `<span class="root-plain-${esc(root)}">${esc(short)}</span>`;
}
function ptypeTagHtml(ptype) {
  const tier = PTYPE_TIER[ptype] || 'amber';
  const label = PTYPE_LABEL[ptype] || ptype;
  return `<span class="tag tptype-${tier}">${esc(label)}</span>`;
}
// ドリルダウン表用：短縮ラベル版（現在は未使用。他画面からの参照用に残置）
function ptypeTagShortHtml(ptype) {
  const tier = PTYPE_TIER[ptype] || 'amber';
  const label = PTYPE_LABEL_SHORT[ptype] || ptype;
  return `<span class="tag tptype-${tier}">${esc(label)}</span>`;
}
// ドリルダウン表用：フル文言をタグではなくプレーンテキストで表示（列幅に応じて折り返す）
function ptypePlainHtml(ptype) {
  const tier = PTYPE_TIER[ptype] || 'amber';
  const label = PTYPE_LABEL[ptype] || ptype;
  return `<span class="ptype-plain-${tier}">${esc(label)}</span>`;
}
function ratingTagHtml(r) {
  return r ? `<span class="tag tev-${esc(r)}">あなたの評価：${esc(r)}</span>` : '';
}

// ── 施策(cls)別集計（常に全事業ベース）──────────────────────────────────
function clsStats() {
  const map = {};
  let grandTotal = 0;
  EVENTS.forEach(e => {
    const c = e.cls || 'データなし';
    if (!map[c]) map[c] = { cls: c, count: 0, budget: 0 };
    map[c].count++;
    map[c].budget += e.budget;
    grandTotal += e.budget;
  });
  return { list: Object.values(map), grandTotal };
}

// ── 法的根拠フィルタ（チャート・施策一覧・ドリルダウンすべてに反映） ─────────
function setRootFilter(val) { rootFilter = val; render('map'); }
function matchesFilter(e) { return !rootFilter || e.root === rootFilter; }
function rootFilterOptions() {
  const totals = {};
  EVENTS.forEach(e => { totals[e.root] = (totals[e.root] || 0) + 1; });
  return ROOT_ORDER.filter(r => totals[r] > 0);
}
function filteredClsBudgets() {
  const map = {};
  let total = 0;
  EVENTS.forEach(e => {
    if (!matchesFilter(e)) return;
    const c = e.cls || 'データなし';
    map[c] = (map[c] || 0) + e.budget;
    total += e.budget;
  });
  return { map, total };
}

// ── 画面切替 ─────────────────────────────────────────────────────────────
function render(screen) {
  curScreen = screen;
  const app = document.getElementById('app');
  if (screen === 'map') renderMap(app);
  else if (screen === 'cls') renderClsDrill(app);
  else if (screen === 'eval') renderEval(app);
  else if (screen === 'guide') renderGuide(app);
  else if (screen === 'summary') renderSummary(app);
}

// ── ①全体像マップ ────────────────────────────────────────────────────────
function renderMap(app) {
  const { list: fullList } = clsStats();
  const { map: filteredMap, total: filteredTotal } = filteredClsBudgets();
  const visible = fullList.filter(s => (filteredMap[s.cls] || 0) > 0);
  const sorted = visible.slice().sort((a,b) => (filteredMap[b.cls] || 0) - (filteredMap[a.cls] || 0));
  const maxBudget = Math.max(...sorted.map(s => filteredMap[s.cls] || 0), 1);
  const filteredCount = EVENTS.filter(matchesFilter).length;

  const filterBtns = [''].concat(rootFilterOptions()).map(r => {
    const label = r || '全事務事業';
    return `<button class="stbtn${rootFilter===r?' active':''}" onclick="setRootFilter('${esc(r)}')">${esc(label)}</button>`;
  }).join('');

  const cards = sorted.map(s => {
    const fBudget = filteredMap[s.cls] || 0;
    const evalTarget = EVENTS.filter(e => (e.cls || 'データなし') === s.cls && matchesFilter(e));
    const evaluated = evalTarget.filter(e => ratings[e.no]).length;
    const barPct = maxBudget ? (fBudget / maxBudget * 100).toFixed(1) : 0;
    const sharePct = filteredTotal ? (fBudget / filteredTotal * 100).toFixed(1) : '0.0';
    return `<div class="clsbox" onclick="openCls('${esc(s.cls)}')">
      <div class="clstop">
        <span class="clsname" title="${esc(s.cls)}">${esc(s.cls)}</span>
        <span class="clsamt">${(fBudget/100000).toFixed(1)}億円 <b>${sharePct}%</b></span>
      </div>
      <div class="clsbar-wrap"><div class="clsbar" style="width:${barPct}%"></div></div>
      <div class="clsmeta">${evalTarget.length}件中 評価済み${evaluated}件</div>
    </div>`;
  }).join('');

  app.innerHTML = `
    <div class="hd">
      <h1>${esc(LABELS.tool_title)}</h1>
      <div class="sub">${esc(LABELS.card_title)}（全${EVENTS.length}件・${esc(LABELS.cls)}${fullList.length}区分）</div>
    </div>
    <div class="card">
      <div class="filterrow">${filterBtns}</div>
      <p class="maphint">${esc(LABELS.cls)}を選ぶ→事務事業を選ぶ→評価する→投票する、という流れで進みます。まずは${esc(LABELS.cls)}のカードを選んでください。上部のボタンを使うと、法定義務の有無によって事業を絞り込めます（バーの長さと％は、絞り込み対象の中でその${esc(LABELS.cls)}が占める規模を表します）。</p>
      <div class="fresult">${filteredCount}件・${(filteredTotal/100000).toFixed(1)}億円・${esc(LABELS.cls)}${sorted.length}区分　タップで選択</div>
      <div class="sec-heading">${esc(LABELS.cls)}一覧</div>
      <div class="clsgrid-wrap"><div class="clsgrid">${cards}</div></div>
    </div>
    <button class="btn btn-o btn-full" onclick="render('summary')">📊 サマリー・投票を見る</button>
    <div class="card" style="font-size:.75rem;color:#6b7280;line-height:1.5;overflow-wrap:anywhere">
      <strong>出典：</strong><a href="${esc(LABELS.source_url)}" target="_blank" style="overflow-wrap:anywhere">${esc(LABELS.source_url)}</a><br>
      北本市 令和6年度事務事業評価<br>
      住民1人あたりコストは人口65,274人（<a href="https://www.digital.go.jp/resources/japandashboard/municipal-finance" target="_blank">デジタル庁 地方財政ダッシュボード</a>）で計算
    </div>`;
}

// ── cls ドリルダウン（opt-in選択） ─────────────────────────────────────────
function openCls(cls) {
  curCls = cls;
  selected = new Set();
  openEvKeys = null; // 次回描画時に「現状継続」以外を開いた既定状態で初期化
  render('cls');
}

function renderClsDrill(app) {
  const evs = EVENTS.filter(e => (e.cls || 'データなし') === curCls && matchesFilter(e));

  // グルーピング軸は行政評価ev一本（現状継続のみ既定で折りたたみ）。
  // 11分類（支援対象×提供形態）は行ごとのバッジで「何をしている事業か」を示すのみで、グルーピングには使わない。
  const groups = {};
  evs.forEach(e => {
    const key = e.ev || 'データなし';
    (groups[key] = groups[key] || []).push(e);
  });
  const orderedKeys = EV_PRIORITY.filter(k => groups[k]).concat(Object.keys(groups).filter(k => !EV_PRIORITY.includes(k)));

  // 開閉状態は openEvKeys に保持し、チェックボックス操作による再描画をまたいで維持する（既定はすべて折りたたみ）
  if (!openEvKeys) {
    openEvKeys = new Set();
  }

  const evRowHtml = e => {
    const checked = selected.has(e.no) ? 'checked' : '';
    return `<tr>
      <td class="evtd-chk"><input type="checkbox" ${checked} onchange="toggleSel('${e.no}')"></td>
      <td class="evtd-name" onclick="toggleSel('${e.no}')">${esc(e.name)}</td>
      <td class="evtd-budget">${(e.budget/100000).toFixed(1)}億円</td>
      <td class="evtd-root">${rootPlainHtml(e.root)}</td>
      <td class="evtd-ptype">${ptypePlainHtml(e.ptype)}</td>
      <td class="evtd-mine">${myRatingCellHtml(ratings[e.no])}</td>
      <td class="evtd-vote">${voteCellStackHtml(peopleAgg && peopleAgg[e.no])}</td>
    </tr>`;
  };

  const evTableHtml = list => `<div class="evtbl-wrap"><table class="evtbl">
    <thead><tr>
      <th class="evtd-chk"></th><th class="evtd-name">事務事業名</th><th class="evtd-budget">金額</th>
      <th class="evtd-root">法定義務</th><th class="evtd-ptype">提供形態</th><th class="evtd-mine">自分の評価</th><th class="evtd-vote">みんなの評価</th>
    </tr></thead>
    <tbody>${list.map(evRowHtml).join('')}</tbody>
  </table></div>`;

  const sections = orderedKeys.map(key => {
    const list = groups[key].slice().sort((a,b) => b.budget - a.budget);
    const sumOku = (list.reduce((s,e)=>s+e.budget,0)/100000).toFixed(1);
    const openAttr = openEvKeys.has(key) ? ' open' : '';
    return `<details class="evsec" data-evkey="${esc(key)}"${openAttr} ontoggle="onEvToggle(this)">
      <summary>行政による評価結果が${esc(key)}の事務事業（${list.length}件・${sumOku}億円）</summary>
      <div class="evsec-body">${evTableHtml(list)}</div>
    </details>`;
  }).join('');

  app.innerHTML = `
    <div class="hd no-print">
      <div class="card-nav">
        <button class="cnav-btn" onclick="render('map')">← マップに戻る</button>
        <span class="cnav-mid-wrap" title="${esc(curCls)}">${esc(curCls)}${rootFilter ? `（${esc(rootFilter)}のみ）` : ''}</span>
      </div>
    </div>
    <div class="card">
      <div class="bbtns" style="margin-bottom:10px">
        <button class="btn btn-o btn-sm" onclick="selectAllCls(true)">全選択</button>
        <button class="btn btn-o btn-sm" onclick="selectAllCls(false)">全解除</button>
        <span style="font-size:.8rem;color:#6b7280;align-self:center">${evs.length}件中 ${selected.size}件選択中</span>
      </div>
      <p class="maphint" style="margin-bottom:10px">タップして展開し、評価したい事務事業にチェックを入れて「選択した事務事業を評価する」を押してください（複数選択できます）。</p>
      ${sections}
    </div>
    <div class="sticky-spacer no-print"></div>
    <div class="sticky-actions no-print">
      <div class="sticky-inner">
        <button class="btn btn-o btn-full" onclick="render('summary')">📊 サマリー・投票を見る</button>
        <button class="btn btn-p btn-full" ${selected.size ? '' : 'disabled'} onclick="startEvalQueue()">選択した事務事業を評価する（${selected.size}件）</button>
      </div>
    </div>`;
}

function toggleSel(no) {
  if (selected.has(no)) selected.delete(no); else selected.add(no);
  reRenderClsPreserveScroll();
}
function onEvToggle(detailsEl) {
  const key = detailsEl.getAttribute('data-evkey');
  if (detailsEl.open) openEvKeys.add(key); else openEvKeys.delete(key);
}
function selectAllCls(all) {
  const evs = EVENTS.filter(e => (e.cls || 'データなし') === curCls && matchesFilter(e));
  selected = all ? new Set(evs.map(e => e.no)) : new Set();
  reRenderClsPreserveScroll();
}
// チェックボックス操作で画面全体を再描画すると、内訳テーブル（.evtbl-wrap）が
// 個別にスクロール領域を持つためスクロール位置が先頭に戻ってしまう。
// 再描画前後でページ全体とテーブルごとのスクロール位置を保存・復元する。
function reRenderClsPreserveScroll() {
  const sy = window.scrollY;
  const wrapScrolls = {};
  document.querySelectorAll('.evsec').forEach(sec => {
    const wrap = sec.querySelector('.evtbl-wrap');
    if (wrap) wrapScrolls[sec.getAttribute('data-evkey')] = wrap.scrollTop;
  });
  render('cls');
  window.scrollTo(0, sy);
  document.querySelectorAll('.evsec').forEach(sec => {
    const key = sec.getAttribute('data-evkey');
    if (key in wrapScrolls) {
      const wrap = sec.querySelector('.evtbl-wrap');
      if (wrap) wrap.scrollTop = wrapScrolls[key];
    }
  });
}

// ── ②個別評価（opt-inキュー） ───────────────────────────────────────────
function startEvalQueue() {
  if (!selected.size) return;
  queue = EVENTS.filter(e => selected.has(e.no)).sort((a,b) => b.budget - a.budget);
  qCursor = 0;
  render('eval');
}

function renderEval(app) {
  if (qCursor < 0) qCursor = 0;
  if (qCursor >= queue.length) qCursor = queue.length - 1;
  const e = queue[qCursor];
  const r = ratings[e.no] || '';
  const rcls = r === '続行' ? 'rk' : r === '廃止' ? 'rh' : r === '見直し' ? 'rf' : '';
  const budgetText = e.budget ? `${fmt(e.budget)}千円` : '—';
  const impact = e.story_impact;
  const hasImpact = impact && impact !== '判断できない';
  const s3text = hasImpact
    ? `この事業がなくなった場合、${impact}という問題が起きると想定されています。`
    : `評価シートに記載されていません。`;
  const pct = Math.round((qCursor + 1) / queue.length * 100);

  app.innerHTML = `
    <div class="hd no-print">
      <div class="card-nav">
        <button class="cnav-btn" onclick="render('cls')" title="${esc(curCls)}の一覧">← ${esc(curCls)}の一覧</button>
        <span class="cnav-mid">${qCursor+1} / ${queue.length} 件目</span>
        <button class="cnav-btn" onclick="render('map')">マップへ</button>
      </div>
      <div style="text-align:right;margin-top:6px">
        <a href="javascript:void(0)" onclick="render('guide')" style="display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.4);color:#fff;padding:4px 10px;border-radius:4px;font-size:.78rem;text-decoration:none">📖 カードの説明</a>
      </div>
    </div>
    <div class="pbwrap no-print"><div class="pbfill" style="width:${pct}%"></div></div>
    <div class="ecard ${rcls}">
      <div class="ename">${esc(e.name)}</div>
      ${LABELS.show_emeta !== false ? `<div class="emeta">${esc(LABELS.no_col)}：${esc(e.no)}　${esc(LABELS.dept)}：${esc(e.dept)}</div>` : ''}
      ${LABELS.show_tags !== false ? `<div class="tags">
        ${rootTagHtml(e.root)}
        ${evTagHtml(e.ev)}
        ${ptypeTagHtml(e.ptype)}
      </div>` : ''}
      ${LABELS.show_desc !== false ? `<div class="story">
        <div class="story-label">目的・事業内容</div>
        <p>${esc(e.story_p1)}</p>
      </div>` : ''}
      ${LABELS.show_budget !== false ? `<div class="ebudget">R6決算：<span class="amt">${budgetText}</span>　<span style="color:#6b7280;font-size:.8rem">（住民1人あたり約${fmt(Math.round(e.budget*1000/LABELS.population))}円/年）</span></div>
      <div style="font-size:.78rem;color:#6b7280;margin:-8px 0 12px">人件費：${personnelCostHtml()}</div>` : ''}
      ${LABELS.show_outcome !== false ? `<div class="story">
        <div class="story-label">成果</div>
        <p>${esc(e.story_p2)}</p>
      </div>` : ''}
      ${LABELS.show_impact !== false ? `<div class="story">
        <div class="story-label">廃止した場合の影響</div>
        <p>${esc(s3text)}</p>
      </div>` : ''}
    </div>
    <div class="sticky-spacer tall no-print"></div>
    <div class="sticky-actions no-print">
      <div class="sticky-inner">
        ${(() => {
          const aiFields = [LABELS.show_desc !== false ? '目的・事業内容' : null, LABELS.show_outcome !== false ? '成果' : null, LABELS.show_impact !== false ? '廃止した場合の影響' : null].filter(Boolean);
          return aiFields.length > 0 ? `<p class="ai-note">※${aiFields.join('、')}の説明文は、評価シートを元にAIが自動生成しています。内容に違和感がある場合や詳細を確認したい場合は、下のリンクから評価シートをご確認ください。</p>` : '';
        })()}
        <a class="btn btn-p btn-full" href="${esc(LABELS.pdf_url)}#page=${e.pdf_page}" target="_blank">📄 評価シートを確認（p.${e.pdf_page}）</a>
        <p class="maphint" style="margin:8px 0">評価（続行/廃止/見直しを選択）するとサマリー・投票画面の自分の評価に反映されます。</p>
        <div class="rbtns">
          <button class="rbtn${r==='続行'?' ak':''}" onclick="rateQueue('続行')">✓ 続行<small>活動内容と予算に納得</small></button>
          <button class="rbtn${r==='廃止'?' ah':''}" onclick="rateQueue('廃止')">✕ 廃止<small>活動内容に納得できない</small></button>
          <button class="rbtn${r==='見直し'?' af':''}" onclick="rateQueue('見直し')">△ 見直し<small>予算に納得できない</small></button>
        </div>
        <div class="nav">
          <button class="btn btn-o btn-sm" onclick="goQueue(-1)" ${qCursor===0?'disabled':''}>◀ 前へ</button>
          <span class="cpos">${qCursor+1} / ${queue.length}</span>
          <button class="btn btn-o btn-sm" onclick="goQueue(1)">次へ ▶</button>
        </div>
      </div>
    </div>`;
}

// ── カードの説明（ガイド画面）─────────────────────────────────────────────
// 評価カードの各項目が、評価シート・事務事業一覧のどこから来ていて、
// どう加工されているか（転記／区分・分類／AI分類／AI要約／固定表示）を説明する。
function procBadge(label) {
  return `<span class="tag tproc-${esc(label)}">${esc(label)}</span>`;
}
function convRow(k, v) {
  return `<div class="row"><span class="k">${esc(k)}</span><span class="v">→${esc(v)}</span></div>`;
}

function renderGuide(app) {
  app.innerHTML = `
    <div class="hd no-print">
      <div class="card-nav">
        <button class="cnav-btn" onclick="render('eval')">← カードに戻る</button>
        <span class="cnav-mid">📖 カードの説明</span>
        <span style="width:80px"></span>
      </div>
    </div>
    <div class="card">
      <p class="gintro">評価カードの各項目が、評価シート・事務事業一覧のどこから来ていて、どう加工されているかを、出どころを起点にした表で説明します。</p>
      <div class="gproc-legend">
        <span>${procBadge('転記')}評価シート・一覧表の記載をそのまま使用</span>
        <span>${procBadge('区分・分類')}シートの回答を一定のルールでタグに変換</span>
        <span>${procBadge('AI分類')}シートの文章をAIが読んで分類</span>
        <span>${procBadge('AI要約')}シートの文章をAIが要約</span>
        <span>${procBadge('固定表示')}シートに該当項目がなく常に同じ表示</span>
      </div>
      <div class="gtbl">
        <div class="grow ghead">
          <div class="gc-item">カード項目</div>
          <div class="gc-src">評価シート・一覧表での出どころ</div>
          <div class="gc-proc">処理</div>
        </div>
        <div class="grow">
          <div class="gc-item">事業名</div>
          <div class="gc-src">事務事業一覧（Excel）の「事務事業名」欄をそのまま使っています。</div>
          <div class="gc-proc">${procBadge('転記')}</div>
        </div>
        ${LABELS.show_emeta !== false ? `<div class="grow">
          <div class="gc-item">${esc(LABELS.no_col)}・${esc(LABELS.dept)}</div>
          <div class="gc-src">事務事業一覧（Excel）の「ページ番号」「担当課」欄をそのまま使っています。</div>
          <div class="gc-proc">${procBadge('転記')}</div>
        </div>` : ''}
        <div class="grow">
          <div class="gc-item">施策（画面上部）</div>
          <div class="gc-src">評価シート（PDF）の「施策」欄（コードと名称）をそのまま使っています。</div>
          <div class="gc-proc">${procBadge('転記')}</div>
        </div>
        ${LABELS.show_tags !== false ? `<div class="grow">
          <div class="gc-item">法定義務タグ</div>
          <div class="gc-src">評価シート末尾の分析設問「国・県・民間ではなく、市が主体的に実施すべき事業か。」への回答。
            <div class="gmap">
              ${convRow('法令で義務付けられている', '法定義務あり')}
              ${convRow('実施すべきである／実施する必要性は低い', '法定義務なし')}
            </div>
          </div>
          <div class="gc-proc">${procBadge('区分・分類')}</div>
        </div>
        <div class="grow">
          <div class="gc-item">行政評価タグ</div>
          <div class="gc-src">事務事業一覧（Excel）の「今後の展開」欄。
            <div class="gmap">
              ${convRow('A_重点化・拡大して継続', '拡大')}
              ${convRow('B_現状のまま継続', '現状継続')}
              ${convRow('C_見直しして継続（詳細が「事業費の縮小」）', '縮小')}
              ${convRow('C_見直しして継続（それ以外の詳細）', '改善（手段変更）')}
              ${convRow('D_休止・廃止等（詳細が「完了」）', '完了')}
              ${convRow('D_休止・廃止等（それ以外の詳細）', '廃止方向')}
            </div>
            市区町村自身による、次年度以降のこの事業の方向性の評価です。住民の評価とは別の指標です。
          </div>
          <div class="gc-proc">${procBadge('区分・分類')}</div>
        </div>
        <div class="grow">
          <div class="gc-item">提供形態タグ</div>
          <div class="gc-src">事務事業一覧の「事業概要」欄の文章をAIが読み、住民への提供のされ方（現金給付か、業者委託か、施設・インフラ整備か等）で分類したものです。分類結果は人の目でも確認・補正しています。評価シートに直接この項目はありません。</div>
          <div class="gc-proc">${procBadge('AI分類')}</div>
        </div>` : ''}
        ${LABELS.show_desc !== false ? `<div class="grow">
          <div class="gc-item">目的・事業内容</div>
          <div class="gc-src">事務事業一覧の「事業概要」欄の文章を、AIが1〜2文に要約したものです。</div>
          <div class="gc-proc">${procBadge('AI要約')}</div>
        </div>` : ''}
        ${LABELS.show_budget !== false ? `<div class="grow">
          <div class="gc-item">決算額</div>
          <div class="gc-src">評価シートの「事務事業のコスト」表、「総事業費」行の「R6決算」列の数値をそのまま使っています。決算額が0円の事業（4件）は「—」と表示されます。北本市はこの決算額に人件費を含みます（下の「人件費」欄参照）。隣に表示される「住民1人あたり約◯円/年」は、この決算額を北本市の人口（${fmt(LABELS.population)}人）で割って算出した参考値で、評価シートには記載されていません。</div>
          <div class="gc-proc">${procBadge('転記')}</div>
        </div>
        <div class="grow">
          <div class="gc-item">人件費</div>
          <div class="gc-src">評価シートを確認し、決算額にどこまで人件費が含まれるかを実態に即して記述しています：「${esc(LABELS.personnel_cost || '確認取れず')}」（全事業共通の表記で、個別の事業ごとに判定しているものではありません）。</div>
          <div class="gc-proc">${procBadge('転記')}</div>
        </div>` : ''}
        ${LABELS.show_outcome !== false ? `<div class="grow">
          <div class="gc-item">成果</div>
          <div class="gc-src">評価シートの「指標名」欄（活動指標・成果指標の名称）の記載をもとに、AIが文章化しています。実績の数値は評価シート上の並び順が事業ごとに揺れるため使用していません。成果を測る指標が設定されていない事業では、その旨を記載しています。</div>
          <div class="gc-proc">${procBadge('AI要約')}</div>
        </div>` : ''}
        ${LABELS.show_impact !== false ? `<div class="grow">
          <div class="gc-item">廃止した場合の影響</div>
          <div class="gc-src">北本市の評価シートには、この事業をやめた場合の影響を記載する専用の欄がありません。そのため、この項目は常に「評価シートに記載されていません。」と表示されます。</div>
          <div class="gc-proc">${procBadge('固定表示')}</div>
        </div>` : ''}
        <div class="grow">
          <div class="gc-item">「📄 評価シートを確認」リンク</div>
          <div class="gc-src">カードの元になった評価シートのPDFの該当ページに直接ジャンプします。</div>
          <div class="gc-proc">${procBadge('転記')}</div>
        </div>
      </div>
      <div class="gitem">
        <div class="glbl">評価ボタン</div>
        <p>
          <span class="rbtn ak" style="display:inline-block;padding:4px 10px;margin:2px 4px 2px 0">✓ 続行</span>活動内容と予算に納得<br>
          <span class="rbtn ah" style="display:inline-block;padding:4px 10px;margin:2px 4px 2px 0">✕ 廃止</span>活動内容に納得できない<br>
          <span class="rbtn af" style="display:inline-block;padding:4px 10px;margin:2px 4px 2px 0">△ 見直し</span>予算に納得できない
        </p>
      </div>
    </div>
    <div class="sticky-spacer no-print"></div>
    <div class="sticky-actions no-print">
      <div class="sticky-inner">
        <button class="btn btn-p btn-full" onclick="render('eval')">← カードに戻る</button>
      </div>
    </div>`;
}

function rateQueue(val) {
  const e = queue[qCursor];
  ratings[e.no] = val;
  localStorage.setItem(LS_KEY, JSON.stringify(ratings));
  if (qCursor < queue.length - 1) {
    qCursor++;
    render('eval');
  } else {
    // 選んだ事業をすべて評価し終えたらマップに戻る（「評価しては戻ってきてを繰り返す」フロー）
    selected = new Set();
    render('cls');
  }
}
function goQueue(dir) {
  const next = qCursor + dir;
  if (next < 0) return;
  if (next >= queue.length) { render('cls'); return; }
  qCursor = next;
  render('eval');
}

// ── ③サマリー・投票 ─────────────────────────────────────────────────────
function renderSummary(app) {
  app.innerHTML = `
    <div class="hd no-print">
      <div class="card-nav">
        <button class="cnav-btn" onclick="render('map')">← マップに戻る</button>
        <span class="cnav-mid">📊 サマリー・投票</span>
      </div>
    </div>
    <div class="card">
      <h2 style="font-size:1rem;font-weight:700;margin-bottom:10px">${esc(LABELS.summary_title)}</h2>
      <div class="no-print" style="margin-bottom:12px">
        <button id="submit-btn" class="btn btn-p btn-sm" onclick="submitToSupabase()">📤 投票する</button>
        <span style="font-size:.8rem;color:#6b7280;margin-left:10px">投票すると、自分の評価がみんなの評価に反映されます。<br>送信されるのは事業番号・評価結果（続行/廃止/見直し）・送信日時のみです。個人情報は一切収集しません。<br>追加で評価した事業がある場合は、再度このボタンから投票できます（同じ事業を重複して送信することはありません）。<br>実際の収集情報は下の📥 生データCSVから閲覧できます。</span>
      </div>
      <div class="no-print" style="margin-bottom:12px;padding-top:12px;border-top:1px solid #eef0f2">
        <button class="btn btn-o btn-sm" onclick="downloadAllEventsCsv()">📥 全事務事業データをCSVでダウンロード（${EVENTS.length}件）</button>
        <span style="font-size:.8rem;color:#6b7280;margin-left:10px">評価対象の全事務事業を、目的・事業内容、成果、廃止した場合の影響も含めて一括ダウンロードできます。行政による公表はPDFのみのため、表計算ソフト等でご自身の分析にご活用ください。</span>
      </div>
      <div id="vote-section"><p style="color:#6b7280;font-size:.85rem">読み込み中...</p></div>
    </div>
    <button class="btn btn-o btn-full no-print" onclick="render('map')">← マップに戻る</button>
    <button class="btn btn-o btn-full no-print" onclick="if(confirm('評価をすべてリセットしますか？')){localStorage.removeItem(LS_KEY);localStorage.removeItem(SUBMITTED_KEY);ratings={};render('map')}">🗑 自分の評価をリセット</button>`;
  loadPeopleData();
}

function getSubmittedNos() {
  try {
    const v = JSON.parse(localStorage.getItem(SUBMITTED_KEY) || '[]');
    return Array.isArray(v) ? v : [];
  } catch (e) { return []; }
}

async function submitToSupabase() {
  const already = new Set(getSubmittedNos());
  const rows = Object.entries(ratings)
    .filter(([no, r]) => r && !already.has(no))
    .map(([no, r]) => ({ municipality_id: MUNICIPALITY_ID, event_no: no, rating: r }));
  if (!rows.length) { alert('新しく評価した事業がありません。'); return; }
  const btn = document.getElementById('submit-btn');
  if (btn) { btn.disabled = true; btn.textContent = '送信中...'; }
  const { error } = await sb.from('ratings').insert(rows);
  if (error) {
    alert('送信エラー: ' + error.message);
    if (btn) { btn.disabled = false; btn.textContent = '📤 投票する'; }
    return;
  }
  rows.forEach(r => already.add(r.event_no));
  localStorage.setItem(SUBMITTED_KEY, JSON.stringify([...already]));
  if (btn) { btn.disabled = false; btn.textContent = '📤 投票する'; }
  alert(`${rows.length}件を送信しました。`);
  loadPeopleData();
}

async function loadPeopleData() {
  const { data, error } = await sb
    .from('ratings').select('event_no,rating').eq('municipality_id', MUNICIPALITY_ID);
  if (error) {
    const section = document.getElementById('vote-section');
    if (section) section.innerHTML = '<p style="color:#ef4444;font-size:.85rem">データの取得に失敗しました。</p>';
    return;
  }
  const agg = {};
  (data || []).forEach(row => {
    if (!agg[row.event_no]) agg[row.event_no] = {'続行':0,'廃止':0,'見直し':0};
    if (agg[row.event_no][row.rating] !== undefined) agg[row.event_no][row.rating]++;
  });
  peopleAgg = agg;
  // サマリー画面は投票セクションだけ差し替え（renderSummary経由だとloadPeopleDataを再度呼び無限ループになるため）。
  // それ以外（マップ・ドリルダウン等）は画面全体を再描画し、ドリルダウンの「みんなの評価」列に反映する。
  if (curScreen === 'summary') renderVoteSection();
  else render(curScreen);
}

function setVoteFilter(v) { voteFilter = v; renderVoteSection(); }

// 対象＝自分が評価した事業 ∪ 誰かが投票済みの事業。voteFilterで絞り込む
function voteRows() {
  if (!peopleAgg) return [];
  return EVENTS.filter(e => {
    const mine = ratings[e.no] || '';
    const agg = peopleAgg[e.no];
    const hasVotes = !!agg && (agg['続行'] + agg['廃止'] + agg['見直し'] > 0);
    if (!mine && !hasVotes) return false;
    if (voteFilter === '') return true;
    if (voteFilter === '未評価') return !mine && hasVotes;
    return mine === voteFilter;
  }).sort((a, b) => b.budget - a.budget);
}

function myRatingCellHtml(r) {
  return r ? `<span class="tag tev-${esc(r)}">${esc(r)}</span>` : '<span style="color:#9ca3af">未評価</span>';
}
function voteCellHtml(agg) {
  const c = agg || {'続行':0,'廃止':0,'見直し':0};
  const total = c['続行'] + c['廃止'] + c['見直し'];
  if (!total) return '<span style="color:#9ca3af">-</span>';
  return `<span class="pc pc-k">続${c['続行']}</span><span class="pc pc-h">廃${c['廃止']}</span><span class="pc pc-f">見${c['見直し']}</span>`;
}
// ドリルダウン表用：列幅が狭いため3つのバッジを縦積みにする版
function voteCellStackHtml(agg) {
  const c = agg || {'続行':0,'廃止':0,'見直し':0};
  const total = c['続行'] + c['廃止'] + c['見直し'];
  if (!total) return '<span style="color:#9ca3af;font-size:.72rem">-</span>';
  return `<div class="vote-stack"><span class="pc pc-k">続${c['続行']}</span><span class="pc pc-h">廃${c['廃止']}</span><span class="pc pc-f">見${c['見直し']}</span></div>`;
}
function classifyStackHtml(e) {
  return `<div class="vtag-stack">${rootTagHtml(e.root)}${ptypeTagHtml(e.ptype)}${evTagHtml(e.ev)}</div>`;
}
function voteCsvText(rows) {
  const header = ['事業番号','事務事業名','施策',LABELS.dept,'金額','法定義務','提供形態','行政評価','自分の評価','続行票','廃止票','見直し票'];
  const csvRows = rows.map(e => {
    const c = peopleAgg[e.no] || {'続行':0,'廃止':0,'見直し':0};
    return [e.no, e.name, e.cls, e.dept, e.budget, e.root, PTYPE_LABEL[e.ptype] || e.ptype, e.ev, ratings[e.no] || '', c['続行'], c['廃止'], c['見直し']];
  });
  return '﻿' + [header, ...csvRows].map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\n');
}
function downloadVoteCsv() {
  const csv = voteCsvText(voteRows());
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv'}));
  a.download = '北本市_評価結果一覧.csv';
  a.click();
}

// 自分で分析したい人向け：評価・投票の状況によらず全事務事業を出力（行政の公表がPDFのみのため）
function allEventsCsvText() {
  const header = ['事業番号','事務事業名',LABELS.cls]
    .concat(LABELS.show_emeta !== false ? [LABELS.dept] : [])
    .concat(LABELS.show_budget !== false ? ['金額(千円)'] : [])
    .concat(LABELS.show_tags !== false ? ['法定義務','提供形態','行政評価'] : [])
    .concat(LABELS.show_desc !== false ? ['目的・事業内容'] : [])
    .concat(LABELS.show_outcome !== false ? ['成果'] : [])
    .concat(LABELS.show_impact !== false ? ['廃止した場合の影響'] : []);
  const csvRows = EVENTS.map(e => {
    const impact = e.story_impact;
    const hasImpact = impact && impact !== '判断できない';
    const impactText = hasImpact
      ? `この事業がなくなった場合、${impact}という問題が起きると想定されています。`
      : '評価シートに記載されていません。';
    return [e.no, e.name, e.cls]
      .concat(LABELS.show_emeta !== false ? [e.dept] : [])
      .concat(LABELS.show_budget !== false ? [e.budget] : [])
      .concat(LABELS.show_tags !== false ? [e.root, PTYPE_LABEL[e.ptype] || e.ptype, e.ev] : [])
      .concat(LABELS.show_desc !== false ? [e.story_p1] : [])
      .concat(LABELS.show_outcome !== false ? [e.story_p2] : [])
      .concat(LABELS.show_impact !== false ? [impactText] : []);
  });
  return '﻿' + [header, ...csvRows].map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\n');
}
function downloadAllEventsCsv() {
  const csv = allEventsCsvText();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv'}));
  a.download = '北本市_事務事業データ一覧.csv';
  a.click();
}

// 透明性確保のための生データ出力：Supabaseに蓄積された全投票ログをそのまま書き出す（現在の絞り込みの影響を受けない）
async function downloadPeopleCsv() {
  const { data, error } = await sb
    .from('ratings').select('id,municipality_id,event_no,rating,submitted_at')
    .eq('municipality_id', MUNICIPALITY_ID).order('submitted_at');
  if (error) { alert('取得エラー: ' + error.message); return; }
  const header = ['id', 'municipality_id', 'event_no', 'rating', 'submitted_at'];
  const csvRows = (data || []).map(r => header.map(k => '"' + String(r[k]).replace(/"/g, '""') + '"').join(','));
  const csv = '﻿' + [header.join(','), ...csvRows].join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], {type: 'text/csv'}));
  a.download = MUNICIPALITY_ID + '_ratings.csv';
  a.click();
}

function renderVoteSection() {
  const section = document.getElementById('vote-section');
  if (!section) return;
  if (!peopleAgg) { section.innerHTML = '<p style="color:#6b7280;font-size:.85rem">読み込み中...</p>'; return; }

  const allData = Object.values(peopleAgg).reduce((a, c) => ({
    '続行': a['続行'] + c['続行'], '廃止': a['廃止'] + c['廃止'], '見直し': a['見直し'] + c['見直し']
  }), {'続行': 0, '廃止': 0, '見直し': 0});
  const totalVotes = allData['続行'] + allData['廃止'] + allData['見直し'];

  if (!totalVotes && !Object.values(ratings).some(r => r)) {
    section.innerHTML = '<p style="color:#6b7280;font-size:.85rem">まだ評価・投票がありません。</p>';
    return;
  }

  const filterOptions = ['', '続行', '廃止', '見直し', '未評価'];
  const filterBtns = filterOptions.map(v => {
    const label = v || '全事務事業';
    return `<button class="stbtn${voteFilter === v ? ' active' : ''}" onclick="setVoteFilter('${esc(v)}')">${esc(label)}</button>`;
  }).join('');

  const rows = voteRows();

  // ブラウザ表示用：6列に圧縮し、セル内で折り返す（横スクロール不要）
  const compactRows = rows.map(e => `<tr>
      <td><div class="evtd-name">${esc(e.name)}</div><div class="vno">No.${esc(e.no)}</div></td>
      <td>${esc(e.cls)}<div class="vsub">${esc(e.dept)}</div></td>
      <td>${fmt(e.budget)}千円</td>
      <td>${classifyStackHtml(e)}</td>
      <td>${myRatingCellHtml(ratings[e.no])}</td>
      <td>${voteCellHtml(peopleAgg[e.no])}</td>
    </tr>`).join('');

  // 印刷・CSV用：完全版10列（画面には出さず@media printでのみ表示）
  const printRows = rows.map(e => `<tr>
      <td>${esc(e.no)}</td>
      <td>${esc(e.name)}</td>
      <td>${esc(e.cls)}</td>
      <td>${esc(e.dept)}</td>
      <td>${fmt(e.budget)}千円</td>
      <td>${rootTagShortHtml(e.root)}</td>
      <td>${ptypeTagHtml(e.ptype)}</td>
      <td>${evTagShortHtml(e.ev)}</td>
      <td>${myRatingCellHtml(ratings[e.no])}</td>
      <td>${voteCellHtml(peopleAgg[e.no])}</td>
    </tr>`).join('');

  section.innerHTML = `
    <div class="sec-heading">投票状況</div>
    <div class="kgrid" style="margin-bottom:12px">
      <div class="kbox kk"><div class="klbl">続行票</div><div class="knum">${allData['続行']}</div></div>
      <div class="kbox kh"><div class="klbl">廃止票</div><div class="knum">${allData['廃止']}</div></div>
      <div class="kbox kf"><div class="klbl">見直し票</div><div class="knum">${allData['見直し']}</div></div>
      <div class="kbox ku"><div class="klbl">総投票数</div><div class="knum">${totalVotes}</div></div>
    </div>
    <div class="filterrow no-print">${filterBtns}</div>
    <div class="bbtns no-print" style="margin-bottom:8px">
      <button class="btn btn-o btn-sm" onclick="window.print()">🖨 印刷（全項目）</button>
      <button class="btn btn-o btn-sm" onclick="downloadVoteCsv()">📥 CSVダウンロード（全項目）</button>
      <button class="btn btn-o btn-sm" onclick="downloadPeopleCsv()">📥 生データCSV</button>
    </div>
    <p style="font-size:.78rem;color:#6b7280;margin-bottom:10px">自分が評価した事務事業、または誰かが投票済みの事務事業を対象に表示しています。上部のボタンを使うと、自分の評価によって表示する事務事業を絞り込めます。</p>
    <div class="votetbl-wrap"><table class="votetbl">
      <thead><tr><th>事務事業名</th><th>施策／担当課</th><th>金額</th><th>分類</th><th>自分の評価</th><th>みんなの評価</th></tr></thead>
      <tbody>${compactRows}</tbody>
    </table></div>
    <div class="votetbl-print"><table class="evtbl">
      <thead><tr>
        <th>${esc(LABELS.no_col)}</th><th>事務事業名</th><th>施策</th><th>${esc(LABELS.dept)}</th><th>金額</th>
        <th>法定義務</th><th>提供形態</th><th>行政評価</th><th>自分の評価</th><th>みんなの評価</th>
      </tr></thead>
      <tbody>${printRows}</tbody>
    </table></div>`;
}

window.onload = load;
"""

# ── HTML ─────────────────────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{LABELS['tool_title']}</title>
<style>{CSS}</style>
</head>
<body>
<div id="app"></div>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<script>
{JS}
</script>
</body>
</html>"""

# ── 出力 ──────────────────────────────────────────────────────────────────
os.makedirs(OUT_DIR, exist_ok=True)
out_path = os.path.join(OUT_DIR, LABELS['output_file'])
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f"生成完了: {out_path}")
print(f"事業件数: {len(events)} 件")
