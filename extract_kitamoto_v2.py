#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北本市 令和6年度事務事業評価 v2抽出スクリプト
  Excel (451件) + PDF (902ページ, 2ページ/事業) → kitamoto_master_v2.csv

v1（kitamoto_master.csv）からの変更点:
  - cls: 政策(8種) → 施策(31種、他自治体と同粒度)
  - budget: 事業費計（人件費除く） → 総事業費（人件費込み）
  - root: 法定義務あり／裁量 → 法定義務あり／法定義務なし（v2 4タグ変換）
  - ev: Excel「今後の展開」(A_/B_/C_/D_ + 詳細) → v2標準6タグ
  - output_name: 「将来にわたる効果・期待する効果」「これまでの取組と成果」「今後の課題」
    の3テキストをラベル区切りで結合（PDF上の行順が事業ごとに揺れるため、
    ラベル単位の段落として結合する安全側の設計。西宮市のoutput_nameテキストブロック
    採用方針を踏襲）
  - outcome_name: 「指標名」欄の2番目（住民向け成果指標）
  - output_val / outcome_val / outcome_eval: 空欄固定（数値列の並び順が不安定なため）
  - story_impact: '判断できない' 固定（廃止影響の専用記述欄が様式に存在しないため）
"""
import csv
import re
import openpyxl
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTTextLine, LTChar, LTAnno

EXCEL_PATH = r"C:\Users\onuma\Desktop\AIの作業場\小さな政府\07_事務事業評価\01_元データ\R6kitamoto_itiran.xlsx"
PDF_PATH   = r"C:\Users\onuma\Desktop\AIの作業場\小さな政府\07_事務事業評価\01_元データ\R6kitamoto_sheet.pdf"
OUT_CSV    = r"C:\Users\onuma\Desktop\AIの作業場\小さな政府\07_事務事業評価\03_パッチ済みデータ\kitamoto_master_v2.csv"


# ── Excel 読み込み ─────────────────────────────────────────────────────────

def load_excel():
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        page, name, bureau, dept, overview, ev, ev_detail = row[:7]
        if not name:
            continue
        rows.append({
            'page':      int(page) if page and str(page).strip().isdigit() else 0,
            'name':      str(name).strip() if name else '',
            'bureau':    str(bureau).strip() if bureau else '',
            'dept':      str(dept).strip() if dept else '',
            'overview':  str(overview).strip() if overview else '',
            'ev_raw':    str(ev).strip() if ev else '',
            'ev_detail_raw': str(ev_detail).strip() if ev_detail else '',
        })
    return rows


# ── ev 変換（v2標準6タグ） ──────────────────────────────────────────────────

def map_ev(ev_raw, ev_detail_raw):
    if ev_raw.startswith('A_'):
        return '拡大'
    if ev_raw.startswith('B_'):
        return '現状継続'
    if ev_raw.startswith('C_'):
        if '事業費の縮小' in ev_detail_raw:
            return '縮小'
        return '改善（手段変更）'
    if ev_raw.startswith('D_'):
        if '完了' in ev_detail_raw:
            return '完了'
        return '廃止方向'
    return '現状継続'


# ── PDF ページテキスト抽出 ─────────────────────────────────────────────────

def get_lines(page):
    lines = []
    for elem in page:
        if not isinstance(elem, LTTextBox):
            continue
        for line in elem:
            if not isinstance(line, LTTextLine):
                continue
            text = ''.join(
                c.get_text() for c in line if isinstance(c, (LTChar, LTAnno))
            ).strip()
            if text:
                lines.append(text)
    return lines


def parse_int(s):
    clean = s.replace(',', '').strip()
    if re.match(r'^\d+$', clean):
        return int(clean)
    return None


# ── cls（施策）抽出 ─────────────────────────────────────────────────────────

STOP_LABELS = {
    '政策', '施策', '基本事業', '主な取組',
    '課長名', '担当名', '電話番号', '個別計画', '対象事業', '予算編成方針の柱',
    '根拠法令', '根拠条例等', '事業期間', '単年度繰返', '概', '要', '事業概要',
}

def _is_stop_label(s):
    return any(s.startswith(lbl) for lbl in STOP_LABELS)

def extract_cls(lines):
    for i, l in enumerate(lines):
        if l.strip() == '施策' and i + 1 < len(lines) and re.match(r'^\d{1,2}$', lines[i+1].strip()):
            code = lines[i+1].strip()
            j = i + 2
            name_parts = []
            while j < len(lines) and not _is_stop_label(lines[j].strip()) and len(name_parts) < 3:
                name_parts.append(lines[j].strip())
                j += 1
            return f"{code} {''.join(name_parts)}"
    return ''


# ── outcome_name（指標名2番目）抽出 ─────────────────────────────────────────

NOISE_EXACT = {'単位'}
HARD_STOP_EXACT = {'計画値', '実績値', '実績の推移', '総事業費', '事業費計'}
HARD_STOP_PAT = re.compile(r'^R\s*\d+$')

def is_noise(s):
    s = s.strip()
    if not s:
        return True
    if s in NOISE_EXACT:
        return True
    if len(s) <= 1:
        return True
    return False

def is_hard_stop(s):
    s = s.strip()
    if s in HARD_STOP_EXACT:
        return True
    if HARD_STOP_PAT.match(s):
        return True
    if parse_int(s) is not None:
        return True
    if re.match(r'^[\d,]+\.\d+$', s):
        return True
    return False

def extract_outcome_name(lines1):
    try:
        idx = next(i for i, l in enumerate(lines1) if l.strip() == '指標名')
    except StopIteration:
        return ''
    cand = []
    for l in lines1[idx+1: idx+1+25]:
        s = l.strip()
        if is_hard_stop(s):
            break
        if is_noise(s):
            continue
        cand.append(s)
    if len(cand) >= 3:
        return ''.join(cand[1:])
    elif len(cand) == 2:
        return cand[1]
    return ''


# ── output_name（3テキスト結合）抽出 ────────────────────────────────────────

NARRATIVE_LABELS = {'将来にわたる効果・期待する効果', 'これまでの取組と成果', '今後の課題'}

def extract_output_name(lines2):
    end_idx = len(lines2)
    for i, l in enumerate(lines2):
        if '重点化' in l:
            end_idx = i
            break
    parts = []
    cur = ''
    for l in lines2[:end_idx]:
        s = l.strip()
        if s in NARRATIVE_LABELS:
            if cur:
                parts.append(cur)
                cur = ''
            continue
        cur += s
    if cur:
        parts.append(cur)
    return '\n'.join(parts)


# ── フォーム1ページ目のパース ─────────────────────────────────────────────

def parse_form1(lines):
    d = {
        'budget': 0,
        'root':   '法定義務なし',
        'q1':     0,
        'cls':    '',
        'outcome_name': '',
    }

    d['cls'] = extract_cls(lines)
    d['outcome_name'] = extract_outcome_name(lines)

    # ── 予算値（R6決算・R6当初予算） ────────────────────────────────────────
    r6k_idx = None
    r6y_idx = None
    for i, l in enumerate(lines):
        stripped = l.strip()
        if stripped == 'R 6決算' and r6k_idx is None:
            r6k_idx = i
        elif stripped == 'R 6当初予算' and r6y_idx is None:
            r6y_idx = i

    def collect_nth_int(start_idx, n, window=30):
        count = 0
        for l in lines[start_idx+1: start_idx+1+window]:
            v = parse_int(l)
            if v is not None:
                count += 1
                if count == n:
                    return v
        return None

    # R6決算 総事業費 = 1番目の整数（人件費込みトータルコスト）
    if r6k_idx is not None:
        v = collect_nth_int(r6k_idx, n=1)
        if v is not None:
            d['budget'] = v

    # 0 ならR6当初予算にフォールバック（総事業費の開示がないため事業費計を採用）
    if d['budget'] == 0 and r6y_idx is not None:
        v = collect_nth_int(r6y_idx, n=1)
        if v is not None and v > 0:
            d['budget'] = v

    # ── Q1（法的根拠） ────────────────────────────────────────────────────
    answers = []
    for i in range(len(lines)):
        if not re.match(r'^[123]$', lines[i].strip()):
            continue
        run = []
        for j in range(i, min(i + 7, len(lines))):
            if re.match(r'^[123]$', lines[j].strip()):
                run.append(int(lines[j].strip()))
            else:
                break
        if len(run) == 7:
            answers = run
            break

    if answers:
        d['q1'] = answers[0]
        d['root'] = '法定義務あり' if answers[0] == 3 else '法定義務なし'

    return d


# ── メイン ────────────────────────────────────────────────────────────────

def main():
    print('Excel 読み込み中...', flush=True)
    excel_rows = load_excel()
    print(f'  Excel: {len(excel_rows)}件', flush=True)

    print('PDF 読み込み中...', flush=True)
    all_pages = list(extract_pages(PDF_PATH))
    print(f'  PDF: {len(all_pages)}ページ', flush=True)

    pdf_events = []
    for i in range(0, len(all_pages) - 1, 2):
        lines1 = get_lines(all_pages[i])
        text1 = '\n'.join(lines1)
        if '事務事業名' not in text1:
            continue
        lines2 = get_lines(all_pages[i+1])
        form1 = parse_form1(lines1)
        form1['output_name'] = extract_output_name(lines2)
        form1['pdf_page'] = i + 1
        pdf_events.append(form1)

    print(f'  PDF から {len(pdf_events)} 件を抽出', flush=True)

    if len(excel_rows) != len(pdf_events):
        print(f'  ⚠ 件数不一致: Excel={len(excel_rows)}, PDF={len(pdf_events)}', flush=True)
    count = min(len(excel_rows), len(pdf_events))

    records = []
    for idx in range(count):
        ex = excel_rows[idx]
        pd = pdf_events[idx]
        records.append({
            'no':           ex['page'],
            'name':         ex['name'],
            'bureau':       ex['bureau'],
            'dept':         ex['dept'],
            'budget':       pd['budget'],
            'root':         pd['root'],
            'ev':           map_ev(ex['ev_raw'], ex['ev_detail_raw']),
            'overview':     ex['overview'],
            'pdf_page':     pd['pdf_page'],
            'cls':          pd['cls'],
            'story_p1':     '',
            'story_p2':     '',
            'story_impact': '判断できない',
            'output_name':  pd['output_name'],
            'output_val':   '',
            'outcome_name': pd['outcome_name'],
            'outcome_val':  '',
            'outcome_eval': '',
        })

    fieldnames = [
        'no', 'name', 'bureau', 'dept', 'budget', 'root', 'ev', 'overview',
        'pdf_page', 'cls', 'story_p1', 'story_p2', 'story_impact',
        'output_name', 'output_val', 'outcome_name', 'outcome_val', 'outcome_eval',
    ]
    with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(records)

    print(f'\n完了: {len(records)}件 → {OUT_CSV}', flush=True)

    # サマリー出力
    from collections import Counter
    root_cnt = Counter(r['root'] for r in records)
    ev_cnt   = Counter(r['ev'] for r in records)
    cls_cnt  = Counter(r['cls'] for r in records)

    out = []
    out.append(f'総件数: {len(records)}')
    out.append('\n--- root分布 ---')
    for k, v in root_cnt.most_common():
        out.append(f'  {k}: {v}件')
    out.append('\n--- ev分布 ---')
    for k, v in ev_cnt.most_common():
        out.append(f'  {k}: {v}件')
    out.append(f'\n--- cls分布（{len(cls_cnt)}種）---')
    for k, v in cls_cnt.most_common():
        out.append(f'  {k!r}: {v}件')

    zero_budget = sum(1 for r in records if r['budget'] == 0)
    out.append(f'\n予算0件: {zero_budget}件')
    empty_cls = sum(1 for r in records if not r['cls'])
    out.append(f'cls空欄: {empty_cls}件')
    empty_outcome = sum(1 for r in records if not r['outcome_name'])
    out.append(f'outcome_name空欄: {empty_outcome}件')

    out.append('\n--- サンプル（先頭5件） ---')
    for r in records[:5]:
        out.append(f"[{r['no']}] {r['name']}")
        out.append(f"  bureau={r['bureau']} / dept={r['dept']}")
        out.append(f"  cls={r['cls']!r}")
        out.append(f"  budget={r['budget']}千円  root={r['root']}  ev={r['ev']}")
        out.append(f"  outcome_name={r['outcome_name']!r}")
        out.append(f"  output_name={r['output_name']!r}")
        out.append('')

    with open(r"C:\Users\onuma\AppData\Local\Temp\claude\c--Users-onuma-Desktop-AI----\045ab420-5ab9-49ff-b3c3-62bea8343a00\scratchpad\extract_v2_report.txt", 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))


if __name__ == '__main__':
    main()
