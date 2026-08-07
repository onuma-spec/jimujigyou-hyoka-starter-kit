# -*- coding: utf-8 -*-
"""
coord_extract_utils.py
pdfminerのextract_text()の文字列順序が信頼できないPDF（複雑な帳票・A3見開き・
LTFigure内にLTCharがフラットに並ぶ構造等）向けの、LTChar座標ベース抽出の共通関数群。
ファイル末尾に、pymupdf(fitz)を使う自治体向けの数値グリッド抽出関数も追加済み
（湖西市, 2026-07-02。get_text("dict")の座標ベース、pdfminerのLTCharとは別実装）。
さらに末尾に、読み取り順序の復元（get_lines_pymupdf_sorted）・指標名の複数行
結合（merge_wrapped_name）の2関数を追加済み（湖西市, 2026-08-07）。

富田林市（07_事務事業評価）の抽出で開発した2つの技法をまとめたもの：

1. 回答スタンプ方式（find_stamps）
   選択式の帳票で「選択済みの回答だけが太字・大サイズで孤立した単一文字として
   描画される」というレイアウト上の特徴を使い、通常の選択肢定義文字列との混同を防ぐ。
   本文サイズが約5pt前後の帳票であれば、サイズ閾値7.0pt・孤立性判定はそのまま流用できる
   可能性が高いが、フォントサイズは自治体ごとに異なるため、まず対象PDFの本文サイズと
   スタンプ候補サイズの分布を確認してから閾値を調整すること
   （`diag_bigfont.py`パターンで size>=X の文字を一覧化して確認する）。

2. 行帯＋列方式（find_label_runs / extract_by_label_column）
   ラベル文字と値テキストが厳密に同じ行・同じy位置にあるとは限らない帳票
   （名前が2行に折り返りラベルが中間に挟まる、ラベルと値のy中心が数pt程度ずれる等）で、
   ラベル自体の正確な座標を先に特定し、隣接ラベルとの中間点を「行帯」の境界とすることで、
   単純な行クラスタリングでは取りこぼす値を正しく再構成する。

使い方の目安：
- 対象PDFで`extract_text()`の出力を目視し、選択肢やラベル・値の順序が入れ替わっている
  箇所が見つかったら、その区間だけこのモジュールの関数に置き換える
  （ページ全体を書き換える必要はなく、崩れている区間だけ座標ベースにするのが効率的）
- 座標値（x範囲・y許容誤差）は自治体のPDFレイアウトごとに異なるため、
  本モジュールの関数はデフォルト値を持つが、対象PDFに合わせて調整が必要
"""
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar


def walk_chars(el, out):
    """LTPage配下のLTCharを再帰的に集める（LTFigure等の入れ子構造でも動作）"""
    if isinstance(el, LTChar):
        out.append(el)
    elif hasattr(el, '__iter__'):
        for c in el:
            walk_chars(c, out)


def get_page_chars(pdf_path, page_idx):
    """指定ページのLTCharリストを返す"""
    for page_layout in extract_pages(pdf_path, page_numbers=[page_idx]):
        chars = []
        walk_chars(page_layout, chars)
        return chars
    return []


def reconstruct_lines(chars, tol=2.0):
    """LTCharをy帯でクラスタリングして (y中心, 行テキスト) のリストを返す（自前の行再構成）。
    通常の`extract_text()`より信頼できるが、ラベルと値のy中心が`tol`を超えてずれる
    帳票では別々の行に分離されてしまう点に注意（その場合はfind_label_runs系の
    座標ベース抽出に切り替えること）。"""
    chars = sorted(chars, key=lambda c: (-(c.y0 + c.y1) / 2, c.x0))
    lines = []
    cur = []
    cur_y = None
    for c in chars:
        ymid = (c.y0 + c.y1) / 2
        if cur_y is None or abs(ymid - cur_y) <= tol:
            cur.append(c)
            if cur_y is None:
                cur_y = ymid
        else:
            lines.append(cur)
            cur = [c]
            cur_y = ymid
    if cur:
        lines.append(cur)
    out = []
    for ln in lines:
        ln_sorted = sorted(ln, key=lambda c: c.x0)
        y = (ln_sorted[0].y0 + ln_sorted[0].y1) / 2
        out.append((y, ''.join(c.get_text() for c in ln_sorted)))
    return out


def find_stamps(chars, size_threshold=7.0, header_y_cutoff=None, run_tol=1.0):
    """『選択済み回答だけ太字・大サイズで孤立して描画される』帳票から回答スタンプを抽出する。

    size_threshold: 本文サイズ（通常4.5〜5.2pt程度）より明確に大きい値を指定。
                     対象PDFで本文とスタンプ候補のサイズ分布を事前確認すること。
    header_y_cutoff: ページ上部の様式ヘッダー（タイトル等）にある孤立文字
                     （年号の数字等）を誤検出しないための除外ライン。ページ高さの
                     8〜9割程度に設定するのが目安（富田林市はA4縦=841.92ptでy1<780）。
    run_tol: 同一文字とみなすy帯・x連続の許容誤差。

    戻り値：孤立した単一文字（LTChar）のリスト。y座標降順（ページ上→下）。
    Boldフラグは使わない（帳票によっては選択済み回答が非Boldの場合があるため、
    サイズと孤立性のみで判定する方が安全）。
    """
    big = [c for c in chars if (c.y1 - c.y0) >= size_threshold]
    if header_y_cutoff is not None:
        big = [c for c in big if c.y1 < header_y_cutoff]
    big.sort(key=lambda c: (-round((c.y0 + c.y1) / 2), c.x0))
    runs = []
    cur = []
    for c in big:
        if not cur:
            cur = [c]
            continue
        prev = cur[-1]
        same_line = abs(((c.y0 + c.y1) / 2) - ((prev.y0 + prev.y1) / 2)) <= run_tol
        touching = (c.x0 - prev.x1) <= run_tol
        if same_line and touching:
            cur.append(c)
        else:
            runs.append(cur)
            cur = [c]
    if cur:
        runs.append(cur)
    return [r[0] for r in runs if len(r) == 1]


def find_label_runs(chars, x_max, tol=1.5):
    """x0<x_maxの文字を、隣接文字が近接している（同一y帯・x連続）ものだけ連結してrunにする。
    reconstruct_lines()と違い、行全体ではなく短いラベル語（見出し等）だけを狙って
    正確なy位置を取るための関数。ラベルが常に特定のx範囲にあることが分かっている
    帳票で使う（対象PDFでラベルの実際のx0範囲を事前に確認すること）。"""
    cand = [c for c in chars if c.x0 < x_max]
    cand.sort(key=lambda c: (-((c.y0 + c.y1) / 2), c.x0))
    runs, cur = [], []
    for c in cand:
        if not cur:
            cur = [c]
            continue
        prev = cur[-1]
        same_line = abs(((c.y0 + c.y1) / 2) - ((prev.y0 + prev.y1) / 2)) <= tol
        touching = (c.x0 - prev.x1) <= tol
        if same_line and touching:
            cur.append(c)
        else:
            runs.append(cur)
            cur = [c]
    if cur:
        runs.append(cur)
    return runs


def find_section_bound(chars, marker, x_max=130):
    """find_label_runsでmarker文字列から始まるrunを探し、そのy中心を返す
    （セクション見出しの座標を特定し、行帯の境界に使う）。"""
    for run in find_label_runs(chars, x_max=x_max):
        if ''.join(c.get_text() for c in run).startswith(marker):
            return (run[0].y0 + run[0].y1) / 2
    return None


def extract_by_label_column(chars, labels_seq, x_label_max, x_col_min, x_col_max,
                             top_bound_y, bottom_bound_y):
    """『行帯＋列』方式の汎用抽出。labels_seq（帳票内での出現順に並んだラベル文字列の
    リスト）それぞれについて、隣接ラベルとの中間点を行帯境界とし、行帯内で
    x∈[x_col_min, x_col_max]にある文字を上→下・左→右で連結して返す。

    labels_seq: 例 ['成果指標１', '成果指標２', '活動指標１', '活動指標２', ...]
                （帳票内で必ずこの順番で出現するもの。順不同の帳票には使えない）
    x_label_max: ラベル自体のx0がこの値未満にあることを前提にラベル位置を特定する
    x_col_min, x_col_max: 値（名前等）を拾うx範囲（ラベル・矢印・数値列を除いた列）
    top_bound_y, bottom_bound_y: 最初/最後のラベルの外側境界
                                  （セクション見出し等のy座標。find_section_boundで取得）

    戻り値：{ラベル文字列: 抽出テキスト} の辞書（見つからないラベルはキーなし）
    """
    label_pos = {}
    for run in find_label_runs(chars, x_max=x_label_max):
        text = ''.join(c.get_text() for c in run)
        for lbl in labels_seq:
            if text.startswith(lbl) and lbl not in label_pos:
                label_pos[lbl] = (run[0].y0 + run[0].y1) / 2

    ys = [label_pos.get(l) for l in labels_seq]
    values = {}
    for i, lbl in enumerate(labels_seq):
        if ys[i] is None:
            continue
        band_top = ys[i - 1] if i > 0 and ys[i - 1] is not None else top_bound_y
        band_bottom = bottom_bound_y
        for j in range(i + 1, len(ys)):
            if ys[j] is not None:
                band_bottom = ys[j]
                break
        top = (band_top + ys[i]) / 2
        bottom = (band_bottom + ys[i]) / 2
        col = [c for c in chars if x_col_min <= c.x0 <= x_col_max
               and bottom <= (c.y0 + c.y1) / 2 <= top]
        col.sort(key=lambda c: (-(c.y0 + c.y1) / 2, c.x0))
        values[lbl] = ''.join(c.get_text() for c in col).strip()
    return values


# ============================================================================
# pymupdf（fitz）版：数値グリッド抽出（湖西市, 2026-07-02で開発）
#
# 上記の関数群はpdfminerのLTChar前提。pymupdfを使う自治体（fitzで文字化けせず
# 読める場合）で、同一指標の複数年度実績が横に並ぶ数値グリッド（例：R5実績/
# R6目標/R6実績/R7目標）を抽出する際に、get_text("text")の行順序ヒューリス
# ティックが破綻するケース向け。湖西市では「達成状況ラベル直前の2数値」という
# 位置ヒューリスティックが142件中19件で欠落・隣接列の誤取得を起こした。
# ============================================================================
import re as _re

_NUM_PAT_DEFAULT = _re.compile(r'^[\d,]+(\.\d+)?%?$')


def get_page_spans_pymupdf(page):
    """pymupdfのpage.get_text("dict")から (text, x0, y0) のスパンリストを返す。"""
    d = page.get_text("dict")
    spans = []
    for block in d['blocks']:
        if 'lines' not in block:
            continue
        for line in block['lines']:
            for s in line['spans']:
                t = s['text'].strip()
                if t:
                    spans.append({'text': t, 'x0': s['bbox'][0], 'y0': s['bbox'][1]})
    return spans


# ============================================================================
# pymupdf（fitz）版：読み取り順序の復元（湖西市, 2026-08-07で発見・追加）
#
# page.get_text("text")（の.splitlines()）はPDFの内部描画順（ストリーム順）で
# テキストを返すため、セル結合された帳票行（1項目が複数行分の高さを持つセルで
# 描画される等）では、視覚的な位置と無関係な場所にテキストが出現することがある
# （湖西市の実例：ある事業の活動内容を示す3行が、同じページのCheck欄の途中に
# 出現していた）。対策はシンプルで、全スパンを(y, x)でソートし直すだけでよい
# ——複雑な列判定ロジック（extract_by_label_column等）が必要な場面とは異なり、
# 単純な「読み取り順序の並べ替え」だけで直る帳票崩れには、まずこちらを試すこと。
# ============================================================================

def get_lines_pymupdf_sorted(page, y_tol=1.0):
    """page.get_text("text").splitlines()の代替。全スパンを(round(y0, 1), x0)で
    ソートしてから返すため、セル結合等でストリーム順が視覚順と食い違う帳票でも
    正しい読み取り順序でテキスト行のリストを得られる。

    y_tol: 同一スパンをy方向でグルーピングする際の丸め桁（round(y0, 1)相当）。
           通常は変更不要。

    使い方の目安：まず対象PDFで通常のget_text("text")の出力とこの関数の出力を
    見比べ、ラベル・値の並びが視覚的な位置（実物PDF画像）と一致するかを確認する
    こと。多くの帳票では両者は一致する（この関数が必要になるのは、セル結合等
    レイアウトが複雑な一部の帳票のみ）。
    """
    spans = get_page_spans_pymupdf(page)
    spans.sort(key=lambda s: (round(s['y0'], 1), s['x0']))
    return [s['text'] for s in spans]


# ============================================================================
# テキスト行方式：指標名の複数行結合（湖西市, 2026-08-07で開発）
#
# 指標名がテキスト行として1行ずつ取れる帳票（座標抽出まではしていない、
# get_text("text")の素朴な行リストで足りるケース）で、名前が2行に折り返る
# ことがある場合の結合ロジック。以前に「単位の位置から逆算して2行目かどうかを
# 判定する」方式を試みて、複数指標が同一ページに混在するケースで誤結合する
# （別指標の名前まで連結してしまう）という失敗をしたため、逆に「名前候補の側が
# 完結した形になっているか」を先に判定する方式に変更したところ安定した。
# ============================================================================
import re as _re2

_YEAR_PAT1_DEFAULT = _re2.compile(r'^Ｒ?R?\d年度$')
_YEAR_PAT2_DEFAULT = _re2.compile(r'^\(?\d{4}年度\)?$')
_DASH_PAT_DEFAULT = _re2.compile(r'^[-－ー―‐]+$')
_NUM_PAT_LINE_DEFAULT = _re2.compile(r'^[\d,]+(\.\d+)?$')
# 名前がこの語尾で終わっていれば「完結した指標名」とみなす。自治体の用語に応じて
# 呼び出し側で拡張・上書きしてよい（湖西市での実例に基づくデフォルト値）。
DEFAULT_TERMINAL_SUFFIX = (
    '数', '率', '額', '割合', '量', '件', '人', '日', '回', '世帯', '箇所', '時間', '台', 'なし',
    '人数', '日数', '件数', '冊数', '部数', '戸', '店', '校', '施設',
)


def merge_wrapped_name(lines, start_idx, terminal_suffix=DEFAULT_TERMINAL_SUFFIX,
                        max_merges=3, header_tokens=frozenset()):
    """lines[start_idx]を名前の1行目として、以降の行を「完結しているか」を
    見ながら結合する（最大max_merges行まで）。戻り値は (結合後の名前, 単位, 次に
    読み進めるべきindex)。

    判定ルール（同一ページに複数指標が併記される帳票での誤結合を防ぐため、
    「名前が完結しているか」を毎回チェックしてから次の行を取り込むかどうかを
    決める）：
      - 名前が terminal_suffix のいずれかで終わる、または閉じ括弧（）/)で
        終わっていれば「完結」とみなし、それ以降の行は結合しない
      - ただし次の候補行が丸括弧で完全に囲まれた注記（例:「（除く）」）の場合は、
        完結済みの名前であっても注記として結合する
      - 候補行が「短い（6字以内）」かつ数字ではなく、次の行が数値であれば、
        それは名前の続きではなく単位とみなして結合を止める（unit に格納）
      - 候補行が年度ラベル（R6年度／(2024年度)等）に一致する場合は無条件に
        結合を止める
      - 開始行が「-」等のダッシュのみの場合は「指標そのものが未設定」とみなし
        結合しない

    header_tokens: 上記の年度ラベル判定に加えて、無条件に結合を止めたい
                   固定文字列があれば渡す（自治体ごとのラベル文言）。
    """
    def is_bracketed(s):
        return s.startswith(('（', '(')) and s.endswith(('）', ')')) and len(s) >= 2

    def is_complete(name):
        return name.endswith(('）', ')')) or name.endswith(terminal_suffix)

    def is_header_like(s):
        return s in header_tokens or _YEAR_PAT1_DEFAULT.match(s) or _YEAR_PAT2_DEFAULT.match(s)

    name = lines[start_idx]
    j = start_idx + 1
    unit = ''
    merges = 0
    if _DASH_PAT_DEFAULT.match(name):
        return name, unit, j
    while j < len(lines) and merges < max_merges:
        cand = lines[j]
        nxt = lines[j + 1] if j + 1 < len(lines) else None
        cand_is_unit = (
            len(cand) <= 6 and not is_bracketed(cand)
            and not _NUM_PAT_LINE_DEFAULT.match(cand)
            and nxt is not None and _NUM_PAT_LINE_DEFAULT.match(nxt)
        )
        if cand_is_unit:
            unit = cand
            j += 1
            break
        if is_header_like(cand):
            break
        if is_bracketed(cand) or not is_complete(name):
            name += cand
            j += 1
            merges += 1
            continue
        break
    return name, unit, j


def extract_grid_value_pymupdf(spans, header_text, num_pat=None,
                                header_tol=5, sub_label=None, sub_label_tol=15,
                                value_y_min=10, value_y_max=40, value_x_tol=20,
                                header_occurrence=0):
    """pymupdfスパンから、指定ヘッダー列直下の数値を座標ベースで抽出する。

    header_text: 列見出しの完全一致テキスト（例: 'R6 2024'）。同じテキストが
                  複数回現れる帳票（目標列・実績列で同名になる等）では
                  header_occurrence で何番目を使うか指定する（0始まり）。
    num_pat: 値とみなす正規表現（デフォルトは整数/カンマ/小数/%を許容）
    sub_label: ヘッダーのサブラベル（例: '実績'）。指定すると、ヘッダーの
               近傍（x許容15pt・y方向0〜15pt下）にこのテキストがあることを
               確認してから値を探す（列の取り違えを防ぐ簡易バリデーション）
    value_y_min/value_y_max: ヘッダーからのy方向オフセット範囲（pt）で値を探す
    value_x_tol: ヘッダーのx0からの許容誤差（pt）

    戻り値：見つかった値の文字列（カンマ・%を除去）。見つからない場合はNone。
    """
    num_pat = num_pat or _NUM_PAT_DEFAULT
    headers = [s for s in spans if s['text'] == header_text]
    if len(headers) <= header_occurrence:
        return None
    # 同じテキストが複数ある場合はx座標昇順に並べて指定インデックスを採用
    same_row_candidates = sorted(
        [s for s in headers if abs(s['y0'] - headers[0]['y0']) < header_tol],
        key=lambda s: s['x0']
    )
    if len(same_row_candidates) <= header_occurrence:
        return None
    header = same_row_candidates[header_occurrence]
    target_x, header_y = header['x0'], header['y0']

    if sub_label:
        sub = [s for s in spans if s['text'] == sub_label
               and abs(s['x0'] - target_x) < sub_label_tol
               and 0 < s['y0'] - header_y < sub_label_tol]
        if not sub:
            return None

    candidates = [
        s for s in spans
        if num_pat.match(s['text'])
        and value_y_min < s['y0'] - header_y < value_y_max
        and abs(s['x0'] - target_x) < value_x_tol
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda s: s['y0'] - header_y)
    return candidates[0]['text'].replace(',', '').replace('%', '')
