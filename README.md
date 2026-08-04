# 事務事業優先度評価ツール スターターキット

行政が公表しているPDF形式の「事務事業評価シート」を住民が読みやすい形に構造化し、住民自身が個々の事業を評価・共有できるツールを、任意の自治体向けに作るためのビルド一式です。

すでに動いている本体ツール（住民向け）は [onuma-spec/jimujigyou-hyoka](https://github.com/onuma-spec/jimujigyou-hyoka) で公開しています。このリポジトリは、その仕組みを**自分の自治体でも作りたい人向け**の制作キットです。

---

## これは何か

一言で言うと、**行政PDFの構造化パイプライン＋住民参加のフレームワーク**です。

| | 中身 |
|---|---|
| 入力 | 自治体が公表する事務事業評価シート（PDF・Excel等） |
| 処理 | Pythonで抽出→AIで住民向けに要約→タグ付け（法的根拠・行政評価の方向性等） |
| 出力 | 単一HTML（GitHub Pagesでそのまま公開可能） |
| 住民参加 | カードごとに「続行／廃止／見直し」を評価し、任意でSupabaseに投票データを送信・集計結果を閲覧 |

対象規模の目安として、これまで7自治体（142件〜652件の事業数）で実績があります。導入自治体一覧・実際に動いているものは[本体リポジトリ](https://github.com/onuma-spec/jimujigyou-hyoka)を参照してください。

---

## 技術構成

- **フロントエンド**：単一HTML（フレームワーク不使用・GitHub Pagesでそのまま配信可能）
- **データ抽出**：Python（`pdfminer.six` / `pymupdf`）でPDFからテキスト・座標を抽出
- **要約生成**：Anthropic API（Claude）で住民向けの説明文を生成
- **住民参加機能**：Supabase（自治体版ごとに新規プロジェクトを個別に用意する設計。庁内システムとは無接続・個人情報は扱わない）

---

## ビルドの流れ

```mermaid
flowchart TD
    subgraph base["常に参照する土台（全フェーズ共通）"]
        FP["fixed_prompt.md<br/>作業手順書の本体"]
        SK["スターターキット.md<br/>独立運用への読み替え層"]
    end

    subgraph p1["フェーズ① 取得・抽出"]
        E1["extract_kitamoto_v2.py<br/>シンプルなPDF抽出の例"]
        E2["extract_tondabayashi_v2.py<br/>座標ベース抽出の例"]
        E3["coord_extract_utils.py<br/>座標抽出の共通関数"]
    end

    subgraph p2["フェーズ② AI要約生成"]
        SG["story_gen_prompt.md<br/>目的・成果の説明文をAI生成"]
    end

    subgraph p3["フェーズ③ HTML生成"]
        BK["build_kitamoto_v3.py<br/>ビルドテンプレート本体"]
    end

    IC["ichinomiya_index.html<br/>完成見本"]

    base -.随時参照.-> p1
    base -.随時参照.-> p2
    base -.随時参照.-> p3

    p1 --> p2 --> p3 --> IC
```

- **土台（`fixed_prompt.md`・`スターターキット.md`）**：特定のフェーズに属さず、①〜③すべての作業中に立ち返って参照する手順書。`スターターキット.md`は`fixed_prompt.md`中の個人アカウント固有の記述を上書きする役割
- **フェーズ①（取得・抽出）**：元データのPDF構造に応じて、シンプルな例（`extract_kitamoto_v2.py`）と座標ベースの例（`extract_tondabayashi_v2.py`）のどちらを参考にするか判断する
- **フェーズ②（AI要約生成）**：抽出したデータをもとに、カードに表示する説明文をAIが生成する
- **フェーズ③（HTML生成）**：`build_kitamoto_v3.py`をコピーして自治体固有の値を埋め、最終HTMLを組み立てる
- **完成見本（`ichinomiya_index.html`）**：①〜③を経て実際にできあがったものの実例

カード内の項目（成果セクション・廃止した場合の影響セクション）は、`LABELS.show_outcome` / `LABELS.show_impact` で表示・非表示を選べます。データの有無ではなく、制作者の好み（カードの情報量をどこまで絞るか）で決めてよい項目です。

---

## 自分の自治体版を作る

**対象読者**：AIコーディング支援（Claude Code等、コード実行可能な環境）が使える方。ブラウザのみのAIチャットでは、PDF抽出のデバッグ作業が現実的に困難です。

1. Python 3系環境を用意し、`pip install pdfminer.six pymupdf openpyxl pandas` を実行
2. このリポジトリを手元にダウンロード（clone または ZIP展開）
3. Claude Codeに `スターターキット.md` を読み込ませて開始を指示する（`スターターキット.md`が読み替えの起点。詳細な作業手順は`fixed_prompt.md`側にある）
4. 対象自治体の事務事業評価シート（PDF等）を用意する。手元にない場合はAIと一緒にWeb検索で探す
5. `ichinomiya_index.html`を完成イメージの見本として、①取得・抽出→②AI要約生成→③HTML生成の順に進める

詰まった場合は`fixed_prompt.md`の該当フェーズの記述に戻ってください。

---

## 免責事項

- 本リポジトリのコードは参考実装です。生成されるツールの内容（抽出結果・AI要約・タグ分類）の正確性は、公開前に必ず一次資料（自治体公表の評価シート原本）と照合してください。
- AIによる要約・分類には誤りが生じる可能性があります。住民に公開する前に、必ず人の目で内容を確認してください。
- 各自治体での公開・運用に伴う法令適合性・業務適合性の確認は、利用者の責任で行ってください。

---

## Contributing

新しい自治体版を作った場合は、ぜひ [Issue](../../issues) で教えてください。[本体ツール](https://github.com/onuma-spec/jimujigyou-hyoka)の導入自治体一覧に追加できる場合があります。

バグ報告・ドキュメント改善の提案も歓迎します。

---

## ライセンス

MIT License
