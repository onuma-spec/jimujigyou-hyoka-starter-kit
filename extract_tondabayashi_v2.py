# -*- coding: utf-8 -*-
"""
富田林市 事務事業評価データ抽出（v2）
令和7年度 事業評価シート（11部門・416件）→ tondabayashi_master_v2.csv

v1（extract_tondabayashi.py）からの変更点:
- root/ev・output_name/outcome_name: extract_text()の並び順が大きく乱れるPDFのため、
  LTChar座標ベースの抽出に変更（回答スタンプ方式・行帯＋列方式）。共通ロジックは
  同フォルダ内 `coord_extract_utils.py` を参照（自治体横断で再利用可能な形に切り出し済み）。
  富田林市固有の座標パラメータ（サイズ閾値・x範囲・ラベル列挙順）はこのファイル内で指定。
- budget: v1と同じ（R6決算・事業費のみ・人件費除く）。人件費込みトータルコストは様式上
  R7予算年度のみしか算出されず決算年度と時点が揃わないため、決算値優先の方針を維持
  （ユーザー確認済み・2026-07-02）。
- law/legal: v2スキーマに存在しないため抽出しない。
- story_impact: 「廃止した場合の影響」専用欄が様式に存在しないため'判断できない'固定。
"""
import re
import csv
import os
import sys
import time
import urllib.request
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

BASE = r"C:\Users\onuma\Desktop\AIの作業場\小さな政府\07_事務事業評価"
sys.path.insert(0, fr"{BASE}\02_抽出スクリプト")
from coord_extract_utils import (
    get_page_chars, find_stamps, find_label_runs, find_section_bound,
    extract_by_label_column,
)
PDFDIR = fr"{BASE}\01_元データ\tondabayashi_pdfs"
OUTCSV = fr"{BASE}\03_パッチ済みデータ\tondabayashi_master_v2.csv"

PDF_SOURCES = [
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/111408.pdf", "市長公室"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110443.pdf", "総務部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110444.pdf", "市民人権部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110445.pdf", "福祉部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110446.pdf", "こども未来部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110447.pdf", "健康推進部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110448.pdf", "まちづくり部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110449.pdf", "産業部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110450.pdf", "教育総務部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110451.pdf", "生涯学習部"),
    ("https://www.city.tondabayashi.lg.jp/uploaded/attachment/110452.pdf", "会計室等"),
]
BUREAU_TO_URL = {dept: url for url, dept in PDF_SOURCES}
# 農業委員会事務局は産業部PDFに同梱
BUREAU_TO_URL["農業委員会事務局"] = BUREAU_TO_URL["産業部"]

ROOT_MAP = {"A": "法定義務あり", "B": "法定義務なし", "C": "法定義務なし", "D": "法定義務なし"}
EV_MAP = {"A": "廃止方向", "B": "現状継続", "C": "拡大"}


def parse_budget_nums(raw):
    comma_nums = re.findall(r"\d{1,3}(?:,\d{3})+", raw)
    if len(comma_nums) >= 3:
        return [int(n.replace(",", "")) for n in comma_nums[:3]]
    digits = re.sub(r"\D", "", raw)
    n = len(digits)
    if n >= 3 and n % 3 == 0:
        size = n // 3
        return [int(digits[i * size:(i + 1) * size]) for i in range(3)]
    nums = [int(x.replace(",", "")) for x in re.findall(r"\d{1,3}(?:,\d{3})+|\d+", raw)]
    return nums if len(nums) >= 3 else [0, 0, 0]


def get_page_count(pdf_path):
    with open(pdf_path, "rb") as f:
        return sum(1 for _ in PDFPage.get_pages(f))


INDICATOR_LABELS_SEQ = ['成果指標１', '成果指標２', '活動指標１', '活動指標２', '活動指標３', '活動指標４']


def find_stamps_tondabayashi(chars):
    """『太字/非太字を問わず、size>=7.0pt・ページ上部の様式ヘッダー(y1>=780)を除いた
    孤立した単一文字』を『選択済み回答スタンプ』として抽出する（富田林市固有の座標）。
    共通ロジックは coord_extract_utils.find_stamps() を使用。"""
    return find_stamps(chars, size_threshold=7.0, header_y_cutoff=780, run_tol=1.0)


def extract_indicators(chars):
    """成果指標１/２・活動指標１〜４の名称をLTChar座標から直接抽出する（富田林市固有の座標）。

    単純な行結合では以下2種の崩れに対応できないため、ラベル自体の正確な座標を
    基準にした「行帯＋列」抽出（coord_extract_utils.extract_by_label_column）を使う：
      - 名前が長く2行に折り返る場合、ラベル行が名前テキストの中間に挟まる
        （例：no.022101「市長会会議出席数（…）」）
      - ラベルと名前テキストのy中心が2〜3pt程度ずれ、通常の行クラスタリング
        許容誤差(2.0pt)を超えて別行に分離される（例：no.022149「情報開示請求件数…」）
    """
    do_y = find_section_bound(chars, '■実施', x_max=130)
    check_y = find_section_bound(chars, '■評価', x_max=130)
    if do_y is None or check_y is None:
        return "", ""

    values = extract_by_label_column(
        chars, INDICATOR_LABELS_SEQ,
        x_label_max=125, x_col_min=122, x_col_max=305,
        top_bound_y=do_y, bottom_bound_y=check_y,
    )

    outcome_name = values.get('成果指標１', '')
    output_name = "、".join(
        values[l] for l in ['活動指標１', '活動指標２', '活動指標３', '活動指標４']
        if values.get(l)
    )
    return output_name, outcome_name


def extract_law_free_fields(text):
    """no/name/bureau/dept/budget/cls/desc（v1のロジックを踏襲。extract_text()ベースで妥当性確認済み）"""
    m = re.search(r"事業番号(\d{6})", text)
    if not m:
        return None
    no = int(m.group(1))

    m = re.search(r"事業番号\d{6}事業名称(.+?)(?=\(目\)|事業目的|施策体系|$)", text)
    name = m.group(1).strip() if m else ""

    m = re.search(r"部署名(.+?)(?=施策体系|■|令和7年度事業評価シート)", text, re.DOTALL)
    bureau = dept = ""
    if m:
        raw = m.group(1).strip()
        parts = raw.split("　")
        if len(parts) >= 2:
            bureau = parts[0].strip()
            dept = parts[1].strip()
        elif parts:
            bureau = parts[0].strip()

    m = re.search(r"施策体系(.+?)(?=■|$)", text)
    cls = ""
    if m:
        parts = m.group(1).split("▶")
        for p in reversed(parts):
            p = p.strip()
            if p and not re.fullmatch(r"[-\s]+", p):
                p = re.split(r"事業目的|事業コスト|事業概要|事業費", p)[0].strip()
                if p:
                    cls = p
                break

    budget = 0
    m = re.search(r"【A】事業費(.*?)【a】", text, re.DOTALL)
    if m:
        nums = parse_budget_nums(m.group(1))
        if len(nums) >= 3:
            budget = nums[1]  # R6決算

    m = re.search(
        r"事業概要[　\s]?(.+?)(?=地方債|令和7年度事業評価シート|予算科目|■実施|令和\d年度事業評価)",
        text, re.DOTALL,
    )
    desc = ""
    if m:
        desc = re.sub(r"\s+", "", m.group(1).strip())[:400]

    return {
        "no": no, "name": name, "bureau": bureau, "dept": dept,
        "budget": budget, "cls": cls, "desc": desc,
    }


def process_pdf(url, dept_name):
    pdf_path = os.path.join(PDFDIR, f"{dept_name}.pdf")
    if not os.path.exists(pdf_path):
        print(f"  Downloading {dept_name}...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            with open(pdf_path, "wb") as f:
                f.write(r.read())
        time.sleep(1)

    n = get_page_count(pdf_path)
    records = []
    skipped = []
    warnings = []
    page_idx = 1
    while page_idx < n:
        text = extract_text(pdf_path, page_numbers=[page_idx])

        if not re.search(r"事業番号\d{6}", text):
            skipped.append(page_idx)
            page_idx += 1
            continue

        main_page_idx = page_idx
        if page_idx + 1 < n:
            next_text = extract_text(pdf_path, page_numbers=[page_idx + 1])
            if (not re.search(r"事業番号\d{6}", next_text)
                    and not re.search(r"事業番号未設定", next_text)):
                text = text + "\n" + next_text
                page_idx += 1

        base = extract_law_free_fields(text)
        if base is None:
            skipped.append(main_page_idx)
            page_idx += 1
            continue

        # root/ev はスタンプ方式（ページ1枚目のみ。診断によりACTION/CHECKは常に1枚目に収まる）
        chars = get_page_chars(pdf_path, main_page_idx)
        stamps = find_stamps_tondabayashi(chars)
        root = ev = ""
        if len(stamps) == 8:
            root_letter = stamps[0].get_text()
            ev_letter = stamps[-1].get_text()
            root = ROOT_MAP.get(root_letter, "判断できない")
            ev = EV_MAP.get(ev_letter, "現状継続")
        else:
            warnings.append((base["no"], len(stamps), [s.get_text() for s in stamps]))
            root = "判断できない"
            ev = "現状継続"

        output_name, outcome_name = extract_indicators(chars)

        records.append({
            **base,
            "root": root,
            "ev": ev,
            "output_name": output_name,
            "outcome_name": outcome_name,
            "story_impact": "判断できない",
            "pdf_page": main_page_idx + 1,
            "bureau_url": BUREAU_TO_URL.get(base["bureau"], url),
        })
        page_idx += 1

    if skipped:
        print(f"  [INFO] スキップ/目次ページ: {skipped}")
    if warnings:
        print(f"  [WARN] スタンプ数!=8: {warnings}")
    return records


all_records = []
for url, dept in PDF_SOURCES:
    print(f"[{dept}]")
    recs = process_pdf(url, dept)
    print(f"  -> {len(recs)}件")
    all_records.extend(recs)

COLS = ["no", "name", "bureau", "dept", "budget", "root", "cls", "ev",
        "desc", "output_name", "outcome_name", "story_impact", "pdf_page", "bureau_url"]

with open(OUTCSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    w.writerows(all_records)

print(f"\n合計: {len(all_records)}件 -> {OUTCSV}")

root_cnt = {}
ev_cnt = {}
for r in all_records:
    root_cnt[r["root"]] = root_cnt.get(r["root"], 0) + 1
    ev_cnt[r["ev"]] = ev_cnt.get(r["ev"], 0) + 1
print("root:", root_cnt)
print("ev:", ev_cnt)
print("budget=0:", sum(1 for r in all_records if r["budget"] == 0))
print("output_name空:", sum(1 for r in all_records if not r["output_name"]))
print("outcome_name空:", sum(1 for r in all_records if not r["outcome_name"]))
