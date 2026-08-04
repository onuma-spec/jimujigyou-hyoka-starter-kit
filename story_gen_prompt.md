# story_gen_prompt.md
# story_p1 / story_p2 バッチ生成ガイド（v2・Anthropic Python SDK版）

## 概要

`seiro_master.csv`（または各自治体のmaster CSV）の各行に対して、住民評価カードに表示する説明文を生成する。  
**生成エンジン**：Anthropic Python SDK（`anthropic` パッケージ）  
**モデル**：`claude-haiku-4-5-20251001`（高速・低コスト）  
**認証**：`~/.claude/.credentials.json` の OAuth トークン（ANTHROPIC_API_KEY 環境変数でも可）  
**注意（2026-08-04追加・朝来市で発覚）**：447件規模の長時間バッチ（1件6〜7秒×件数≒40〜50分以上）ではOAuthトークンが実行途中で失効し、以降の行が全て失敗する事例が発生した。300件を超えるような長時間バッチでは`ANTHROPIC_API_KEY`環境変数の使用を推奨する。

---

## 生成対象フィールド

| フィールド | カード内の役割（ラベル） | 文字数目安 | 生成パス |
|---|---|---|---|
| `story_p1` | 目的・事業内容 | 40〜80字、1〜2文 | 第1パス（story_p1のみ） |
| `story_p2` | 成果 | 50〜100字、1〜2文 | 第2パス（story_p2のみ） |

`story_impact`（廃止した場合の影響）は AI 生成ではなく、評価シートの廃止影響欄から **抽出** する。

**注意**：`build_XX.py`側の`LABELS.show_desc`／`LABELS.show_outcome`は、データの有無ではなく利用者（制作者）の
好みで`False`にできる（fixed_prompt.md参照。カードの情報量を減らしたい場合等）。利用者が「目的・事業内容／
成果セクションは不要」と判断した場合は、本ファイルによる該当パス（story_p1／story_p2）のAI生成自体を
実行不要（API呼び出しの節約）。ただし省略する前に必ず利用者へ確認すること（fixed_prompt.md参照）。

---

## 重要：2パス生成

story_p1 と story_p2 は **別々のパスで生成する**。  
理由：story_p2 のプロンプト・品質基準が異なり、再生成のスコープを分けるため。

- **第1パス**：`if row.get('story_p1'): continue`（p1が空の行のみ生成）
- **第2パス**：`if row.get('story_p2'): continue`（p2が空の行のみ生成）

gen_story.py のデフォルトは **第2パス（story_p2のみ）**。  
story_p1 を再生成したい場合は、スキップ条件と出力フィールドを変更する。

---

## story_p1 プロンプトテンプレート

```
以下の自治体事業情報をもとに、住民が行政サービスの目的と内容を理解するための説明文をJSONで生成してください。JSONのみ出力し、前後の解説文は不要です。

事業名：{name}
事業概要：{overview}

出力ルール：
- story_p1：事業概要（overview）に書かれている内容のみを使い、目的と実施内容を1〜2文（40〜80字）に圧縮する。
- 目的がoverviewに明記されている場合はそれを使う。明記されていない場合、無理に「〜のために」という目的節を作らず、実施内容の要約のみにする。
- overviewに書かれていない目的・意義・背景を、一般常識や外部知識で補って書き足さない（存在しない情報の創作禁止）。
- 「令和○年度」「令和N年度」「R○年度」のような年度表現は絶対に使わない。
- 「市」「町」「区」などの自治体種別は文中に含めない。

出力形式（このJSONのみ返す）：
{"story_p1": "..."}
```

**2026-07-02追加修正（湖西市で発覚）**：story_p1のプロンプトには元々年度表現の禁止ルールがなく、事業概要（overview）に「令和6年度の税制改正に伴い〜」等の年度表現がそのまま含まれる場合、AIがそれを引き写してしまう不具合が湖西市で4件発生した（story_p2側は既に禁止ルールがあったため無事）。story_p1側にも同じ禁止ルールを追加。

**2026-08-04追加修正（朝来市で発覚）**：旧プロンプトは「『〜のために〜しています。』の流れで自然な日本語にする」という文型を要求しており、overviewに目的が明記されていない場合でもAIが一般常識で目的を補完してしまう不具合があった（例：国勢調査事業、overview「令和７年国勢調査の円滑な執行を図る。〇令和７年国勢調査準備事務〇調査区設定業務...」に対し、story_p1が「正確な人口統計の把握と今後の行政施策の基礎となるデータを得るために」というoverviewのどこにも書かれていない目的節を追加していた）。文字数比較（story_p1がoverviewより長い）で検出できた。目的節の強制を外し、overviewにない情報を補わない禁止事項を追加した。あわせて、旧品質チェックの「概要の単なる言い換えになっていないか」は忠実な抜粋・圧縮をむしろNG扱いする内容だったため削除した（下記「品質チェック」節参照）。

---

## story_p2 プロンプトテンプレート（現行・コストなし・年度表現禁止）

```
以下の自治体事業情報をもとに、住民が事業の成果を判断するための説明文をJSONで生成してください。JSONのみ出力し、前後の解説文は不要です。

事業名：{name}
活動指標：{output_name}　実績：{output_val}
成果指標：{outcome_name}　実績：{outcome_val}　評価：{outcome_eval}

出力ルール：
- story_p2：活動指標と成果指標の実績を中心に1〜2文（50〜100字）。「令和○年度」「令和N年度」のような年度表現は使わない。
- 成果指標に実際の指標名がある場合：その指標名と評価内容を踏まえて成果を記述する。実績の数値が「データなし」で具体的な数値が無くても、「成果を測る指標は設定されていません」とは書かない（指標自体は設定されているため誤りになる）。数値が無い場合は指標名と評価内容の説明にとどめる。
- 成果指標名が「データなし」または空白の場合：
  - 活動指標にデータがある → 活動指標の実績のみで1文にまとめ、「成果を測る指標は設定されていません。」を追記する。
  - 活動指標も空欄・データなし → 「成果を測る指標が設定されていません。」のみ出力する。
- 評価が「評価対象外」の場合、評価には触れず活動指標の実績のみで記述する。
- 具体的な金額・千円単位の数値は書かない（件数・人数・回数・割合(%)などの活動量は書いてよい）。
- 「市」「町」「区」などの自治体種別は文中に含めない。

出力形式（このJSONのみ返す）：
{"story_p2": "..."}
```

**2026-07-01更新**：outcome_nameがデータなしでもoutput_nameにデータがある場合は活動内容を残すルールに変更（v2全体の標準ルール）。理由：story_p1（目的・事業内容）とstory_p2（成果）は役割が異なり、活動指標の情報を丸ごと捨てるのは不親切なため。聖籠町はoutput_nameが空欄0件・outcome_nameがデータなし0件のため、このルール変更による既存データへの影響はない。

**2026-07-01追加修正（西宮市で発覚）**：outcome_nameが実在するのにoutcome_valを「データなし」固定にする自治体では、AIが「成果を測る指標は設定されていません」を誤って付ける不具合が起きる（西宮市で142件中136件・95.8%発生）。「指標名がある場合は実績値がなくても『設定されていません』と書かない」ルールを追加して解消。**次回以降の自治体でも、outcome_nameが実在するのにoutcome_valを取得しない設計にする場合は、生成後に必ず「outcome_nameが実在するのに『設定されていません』を含む」件数をチェックすること。**

**2026-07-02追加修正（湖西市で発覚・重要）**：上記の是正ルールは西宮市の`fix_p2_*.py`（後付けの修正専用スクリプト）にしか反映されておらず、**この節の「gen_story.py（現行コード）」に埋め込まれたプロンプト本体には反映されていなかった**。そのため湖西市は一番最初のv2移行だったこともあり、is-not-set誤記載が142件中129件（91%）発生。さらに、outcome_val抽出漏れを直した後にこのコード片のプロンプトで再生成した際、同じ誤記載が15件で**再発**した（是正ルールがコード自体に組み込まれていなかったため）。**この節のコード片こそが今後全自治体でコピーされる原本なので、プロンプト本文と実コードの内容を必ず同期させること。** 今回、両方に「指標があるのに設定されていないと書かない」ルールと「金額・千円表現の禁止」ルールを追記して同期済み（2026-07-02）。次に新しいルールを追加する際も、本文の説明だけでなく本節のコード片も同時に更新すること。

**禁止事項（story_p2）**：
- コスト・予算の記載（カード内の「R6決算」表示と重複するため）
- 「令和○年度」等の年度表現（データが古くなっても違和感が出ないようにするため）

**2026-08-04追加修正（朝来市で発覚）**：output_name・outcome_nameが両方とも空欄／データなしの行で、プロンプトに明記したルール（「成果を測る指標が設定されていません。」のみ出力）にAIが従わずJSON生成を拒否するケースが複数発生した。この状態は出力が一意に定まる決定的なケースなので、そもそもAPI呼び出しに頼らず、`gen_story.py`側で機械的に固定文言を埋める分岐を追加した（下記コード参照）。ルールをプロンプトに書いてAIの遵守に賭けるより、決定的なケースはコード側で確定させる方が確実かつ低コスト。

---

## gen_story.py（現行コード・story_p2生成専用）

```python
"""
gen_story.py
seiro_master.csv の各行に story_p2 を AI 生成して書き戻す（第2パス）。
Anthropic Python SDK を使用。
"""

import csv, json, sys, time
from pathlib import Path

# ===== 自治体ごとに変更する =====
CSV_PATH   = r'C:\Users\onuma\Desktop\AIの作業場\小さな政府\07_事務事業評価\加工データ\seiro_master.csv'
POPULATION = 14000  # 住民人口（story_p1生成時のみ使用）
MODEL      = 'claude-haiku-4-5-20251001'
# ================================

def get_client():
    import anthropic, os
    if os.environ.get('ANTHROPIC_API_KEY'):
        return anthropic.Anthropic()
    cred_path = Path.home() / '.claude' / '.credentials.json'
    if cred_path.exists():
        data = json.loads(cred_path.read_text(encoding='utf-8'))
        token = data.get('claudeAiOauth', {}).get('accessToken', '')
        if token:
            return anthropic.Anthropic(auth_token=token)
    raise RuntimeError('認証情報が見つかりません。ANTHROPIC_API_KEY を設定してください。')

def run_claude(client, prompt: str) -> dict:
    import anthropic as _ant
    for attempt in range(5):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=512,
                messages=[{'role': 'user', 'content': prompt}],
            )
            text = msg.content[0].text.strip()
            start = text.find('{')
            end   = text.rfind('}') + 1
            if start < 0 or end <= 0:
                raise ValueError(f'JSON not found: {text[:200]}')
            return json.loads(text[start:end])
        except _ant.RateLimitError:
            wait = 60 * (attempt + 1)
            print(f'  [429] レート制限。{wait}秒待機中...', flush=True)
            time.sleep(wait)
    raise RuntimeError('429 が繰り返し発生。中断します。')

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    client = get_client()

    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    def _is_empty(v):
        return not v or v.strip() in ('', 'データなし', '成果指標なし')

    total = len(rows)
    for i, row in enumerate(rows):
        if row.get('story_p2'):          # ← 第2パス：p2が空の行のみ生成
            print(f'[skip] {i+1}/{total} {row["name"][:25]}')
            continue

        # 活動指標・成果指標が両方とも空欄／データなしの場合は出力が一意に定まるため、
        # API呼び出しをせず固定文言で埋める（2026-08-04・朝来市で発覚：AIがルールに従わず生成拒否するケースがあった）
        if _is_empty(row.get('output_name', '')) and _is_empty(row.get('outcome_name', '')):
            row['story_p2'] = '成果を測る指標が設定されていません。'
            print(f'[fix]  {i+1}/{total} {row["name"][:25]} (両方空欄→固定文言・API不使用)')
            continue

        prompt = f"""以下の自治体事業情報をもとに、住民が成果を判断するための説明文をJSONで生成してください。JSONのみ出力し、前後の解説文は不要です。

事業名：{row['name']}
活動指標：{row['output_name']}　実績：{row['output_val']}
成果指標：{row['outcome_name']}　実績：{row['outcome_val']}　評価：{row['outcome_eval']}

出力ルール：
- story_p2：活動指標と成果指標の実績を中心に1〜2文（50〜100字）。「令和○年度」「令和N年度」「R○年度」のような年度表現は絶対に使わない。
- 成果指標に実際の指標名がある場合：その指標名と評価内容を踏まえて成果を記述する。実績の数値が「データなし」で具体的な数値が無くても、「成果を測る指標は設定されていません」とは絶対に書かない（指標自体は設定されているため誤りになる）。数値が無い場合は指標名と評価内容の説明にとどめる。
- outcome_nameが「データなし」または空白の場合：
  - output_nameにデータがある → 活動指標の実績のみで1文にまとめ、「成果を測る指標は設定されていません。」を追記する。
  - output_nameも空欄・データなし → 「成果を測る指標が設定されていません。」のみ出力する。
- 具体的な金額・千円単位の数値は書かない（件数・人数・回数・割合(%)などの活動量は書いてよい）。
- 「市」「町」「区」などの自治体種別は文中に含めない。

出力形式（このJSONのみ返す）：
{{"story_p2": "..."}}"""

        try:
            result = run_claude(client, prompt)
            row['story_p2'] = result.get('story_p2', '').strip()
            print(f'[OK]  {i+1}/{total} {row["name"][:25]}')
        except Exception as e:
            row['story_p2'] = ''
            print(f'[ERR] {i+1}/{total} {row["name"][:25]}: {e}', file=sys.stderr)

        time.sleep(5)  # レート制限対策（OAuth トークン経由は制限が厳しいため長めに設定）

    with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'\n完了。{CSV_PATH} に書き戻しました。')

if __name__ == '__main__':
    main()
```

---

## 実行手順

1. `CSV_PATH` を自治体に合わせて編集する
2. master CSV に `story_p1` `story_p2` 列が存在することを確認（空でOK）
3. 第1パス（story_p1 生成）：スキップ条件を `story_p1`、出力を `story_p1` に変更して実行
4. 第2パス（story_p2 生成）：デフォルト設定のまま実行
   ```
   python "C:\Users\onuma\Desktop\AIの作業場\小さな政府\07_事務事業評価\スクリプト\gen_story.py"
   ```
   300件を超える規模の自治体では、OAuthトークンの途中失効を避けるため`ANTHROPIC_API_KEY`環境変数の使用を推奨（上記「概要」節の注意参照）。
5. エラー行は空のままなので、再実行すれば自動的に再生成される

---

## 品質チェック（生成後に目視確認）

**story_p1**
- [ ] overviewに書かれていない目的・意義・背景を一般常識で補っていないか（機械的にstory_p1の文字数がoverviewの文字数を超えていないか全件比較すると、補完の疑いがある行を効率的に検出できる。朝来市447件中1件で発見）
- [ ] 「令和○年度」等の年度表現が含まれていないか（overview側に年度表現があると引き写されやすい）
- [ ] 不自然な文や異常な長さ（10字以下・200字以上）がないか

**story_p2**
- [ ] コスト・予算の記載が含まれていないか（含まれていれば手動削除）
- [ ] 「令和○年度」等の年度表現が含まれていないか
- [ ] outcome_nameが実在するのに「成果を測る指標は/が設定されていません」と誤記載していないか（outcome_nameが「データなし」「成果指標なし」等のセンチネル値の行は除外して判定すること。誤って含めると正しい記載まで再生成対象になり、無駄なAPI呼び出しと文言劣化を招く＝湖西市で実際に発生）
- [ ] 逆方向の誤記載（outcome_nameがセンチネル値＝指標なしなのに「成果指標は設定されています」等、存在する体で書いていないか）もチェックする（湖西市で2件発見）
- [ ] 成果指標なし・活動指標もなしの場合に「成果を測る指標が設定されていません。」のみ出力されているか
- [ ] 成果指標なし・活動指標ありの場合に活動内容＋「成果を測る指標は設定されていません。」の形になっているか
- [ ] 不自然な文や異常な長さ（10字以下・200字以上）がないか
- [ ] 問題行は CSV を直接編集するか、本ファイルの是正済みプロンプトで対象行のみ再生成する（元のgen_story.pyプロンプトで再生成すると同じ不具合が再発しうるため、必ず本ファイル最新版のプロンプトを使うこと）

**抽出フィールド自体の再検証（outcome_val等、数値テーブルの抽出結果）**
- [ ] ラベル直前/直後のN行という位置ヒューリスティックで数値テーブル（同一指標の複数年度実績等）を抽出している場合、`get_text("dict")`等の座標ベースで数件を検算し、欠落・隣接列との混同がないか確認する（湖西市で19/142件の欠落・誤取得が発覚。詳細：[[project-gyosei-hyoka]]内「湖西市 outcome_val抽出バグ修正」節）
- [ ] 抽出ロジックを後から修正してCSVの値を書き換えた場合、影響を受けた行のstory_p1/p2は必ず空欄化して再生成する（値と説明文の不整合を防ぐ）

---

## 処理時間の目安

- 1件あたり：約6〜7秒（5秒スリープ＋API応答1〜2秒）
- 224件（聖籠町）：約25〜30分
- 途中中断した場合：再実行すると生成済み行をスキップするため、続きから再開できる
