r"""
patch_show_labels.py
生成済みHTML（build_html.py等のshow_*対応テンプレート由来）の LABELS のうち、
評価カードの表示制御フラグ（show_*）だけを、再ビルドなしで書き換えるツール。

背景：評価カードの各セクション（事業番号・担当課／タグ／目的・事業内容／決算額・人件費／成果／
廃止した場合の影響）は LABELS.show_* で表示・非表示を切り替えられるが、従来は Python の
LABELS 辞書を編集して build_html.py を再実行する必要があった。本スクリプトは、既にビルド済みの
HTML ファイルの LABELS ブロックだけを直接書き換えることで、データ（EVENTS配列の
story_p1/p2・タグ・予算等）には一切触れずに表示だけを何度でも変更できるようにする。

前提：対象HTMLのJS側に `LABELS.show_desc !== false` 等の条件分岐が既に存在すること。
2026-08-04以降の build_html.py 系テンプレートでビルドされたファイルのみ有効。
既存7自治体（西宮市・北本市・湖西市・品川区・富田林市・聖籠町・一宮市）は
このJS側ロジック自体がまだ存在しないため非対応（別途移植が必要）。

対象キー（安全のため、この6つ以外は変更できない）：
show_emeta, show_tags, show_desc, show_budget, show_outcome, show_impact

※ enable_voting（投票機能／Supabase連携のオンオフ）は意図的に対象外。show_*が「カードの
どのセクションを見せるか」という同種の設定なのに対し、enable_voting は複数の関数
（submitToSupabase・loadPeopleData・renderVoteSection等）に分散した機能全体のオンオフであり、
ビルドによってはJS側の対応が一部漏れていることがある（2026-08-05・朝来市の試作ビルドで実際に
発覚：LABELSにenable_votingの値はあってもJS側に読み取り箇所が1つも無く、値を書き換えても
何も変わらなかった）。この種の機能トグルは、値を書き換えるだけでは安全に反映される保証がなく、
再ビルドして初めてJS側の実装を確認できるため、このツールでは扱わない。

使い方：
  python patch_show_labels.py <html_file> --show-desc false --show-tags true
  python patch_show_labels.py <html_file> --dry-run --show-tags false

何度でも実行可能。実行のたびに直前の状態を <html_file>.bak にバックアップする
（--no-backup で無効化可）。

バックアップから元に戻す方法：
  <html_file>.bak を <html_file> という名前でコピーし直すだけでよい（Windowsの場合）
  copy <html_file>.bak <html_file>
  ※ .bak は「直前の1回分」しか保持しない。連続して実行すると古いバックアップは
  上書きされるため、複数世代残したい場合は都度別名で退避すること。
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ALLOWED_KEYS = [
    'show_emeta', 'show_tags', 'show_desc',
    'show_budget', 'show_outcome', 'show_impact',
]


def str2bool(v):
    if v.lower() in ('true', '1', 'yes'):
        return True
    if v.lower() in ('false', '0', 'no'):
        return False
    raise argparse.ArgumentTypeError(f'true/falseで指定してください: {v}')


def extract_labels_json(html_text):
    """`const LABELS = {...};` を波括弧の対応を数えて安全に抽出する（開始位置, 終了位置）を返す。
    文字列中の { } はカウントしないよう、ダブルクォート・エスケープを考慮する。"""
    marker = 'const LABELS = '
    start = html_text.find(marker)
    if start < 0:
        raise ValueError('HTML内に `const LABELS = ` が見つかりません')
    brace_start = html_text.find('{', start)
    if brace_start < 0:
        raise ValueError('LABELSのJSON開始位置(`{`)が見つかりません')

    depth = 0
    in_string = False
    escape = False
    i = brace_start
    while i < len(html_text):
        ch = html_text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return brace_start, i + 1  # end は exclusive
        i += 1
    raise ValueError('LABELSのJSON終端(`}`)が見つかりません（波括弧が対応していません）')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('html_file', help='対象のHTMLファイルパス')
    for key in ALLOWED_KEYS:
        flag = '--' + key.replace('_', '-')
        parser.add_argument(flag, dest=key, type=str2bool, default=None,
                             help=f'{key} を true/false で上書き（省略時は変更しない）')
    parser.add_argument('--dry-run', action='store_true', help='書き込まず変更内容だけ表示する')
    parser.add_argument('--no-backup', action='store_true', help='.bak バックアップを作らない（非推奨）')
    args = parser.parse_args()

    overrides = {k: getattr(args, k) for k in ALLOWED_KEYS if getattr(args, k) is not None}
    if not overrides:
        print('変更対象が指定されていません。--show-desc false のように少なくとも1つ指定してください。',
              file=sys.stderr)
        sys.exit(1)

    path = Path(args.html_file)
    if not path.exists():
        print(f'ファイルが見つかりません: {path}', file=sys.stderr)
        sys.exit(1)
    html_text = path.read_text(encoding='utf-8')

    try:
        start, end = extract_labels_json(html_text)
        labels = json.loads(html_text[start:end])
    except ValueError as e:
        print(f'エラー: {e}', file=sys.stderr)
        print('このHTMLは show_* 対応テンプレート（build_html.py等）由来ではない可能性があります。',
              file=sys.stderr)
        sys.exit(1)

    print(f'対象ファイル: {path}')
    changed = False
    for key, new_val in overrides.items():
        old_val = labels.get(key, '(未設定・JS側では true 相当として扱われる)')
        if old_val != new_val:
            print(f'  {key}: {old_val} -> {new_val}')
            changed = True
        else:
            print(f'  {key}: {old_val} (変更なし)')
        labels[key] = new_val

    if not changed:
        print('全て現在値と同じでした。変更はありません。')
        return

    new_json_text = json.dumps(labels, ensure_ascii=False)
    new_html = html_text[:start] + new_json_text + html_text[end:]

    if args.dry_run:
        print('\n--dry-run のため書き込みは行っていません。')
        return

    if not args.no_backup:
        backup_path = path.with_suffix(path.suffix + '.bak')
        shutil.copy2(path, backup_path)
        print(f'バックアップ: {backup_path}')

    path.write_text(new_html, encoding='utf-8')
    print(f'{path} を更新しました。')


if __name__ == '__main__':
    main()
