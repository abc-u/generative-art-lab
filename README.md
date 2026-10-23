# Generative Art Lab

日本語で、ジェネラティブアートの考え方を見て・動かして・つくりながら学ぶ静的サイトです。GitHub Pages の `main` / `/(root)` から配信できます。外部ビルドやJavaScriptライブラリは使いません。

## 公開

- Repository: https://github.com/abc-u/generative-art-lab
- URL: https://abc-u.github.io/generative-art-lab/
- Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/(root)`

`index.html`、`lesson.html`、`styles.css`、`app.js` がサイト共通部分です。トップページにはシードを変えて見比べるスタディギャラリーがあります。Dayごとの教材データは `lessons/day-NN.json`、カリキュラム一覧は `curriculum.json` に置きます。Day 1の詳細ページとデモは `lesson.html` / `lesson.js` に含まれます。各Dayは共通テンプレートから表示され、完了状況はブラウザの localStorage に保存されます。

## 日次レッスンの運用

`.github/workflows/daily-lesson.yml` は毎日 09:00 JST に実行されます。GitHub Actions の **Repository Settings → Secrets and variables → Actions → New repository secret** で `OPENAI_API_KEY` を登録してください。ChatGPTの契約とOpenAI APIの認証・料金は別です。APIキーはGitHub Secretにのみ保存し、コードやサイトへ書かないでください。

ワークフローは公開済みのDay数から次のDay番号を決め、公開済みレッスンとのつながりをもとに新しいテーマを選び、`gpt-4.1-mini` と Responses API のJSON Schema出力で教材・自己完結型デモを作ります。必須セクション、Day順序と重複、URL形式、コードとデモJavaScriptの構文、Canvasと操作UI、実験ステップからデモを変更する設定、外部通信・外部アセットの禁止を検査します。検査を通らない内容はPull Requestになりません。すでに未レビューの自動生成Pull Requestがある間は、次のスケジュール実行をスキップします。

生成教材は `automation/daily-lesson` ブランチのPull Requestとして提出されます。これは公開前に日本語の説明、数値計算、作品の参照元、デモ操作を人が確認するためです。レビュー後に `main` へマージするとPagesが公開します。マージせずにPRを保留しても、現在の公開サイトは変わりません。生成エラーや参照の不確かさがあれば、Actions → Daily lesson draft の実行ログを確認し、修正後に手動で再実行できます。

Actions → **Daily lesson draft → Run workflow** から手動実行できます。GitHub Actions の自動起動を有効にしておく必要があります。APIキーがまだ設定されていない間、日次ワークフローは生成段階で失敗し、公開中のサイトやカリキュラムは変更されません。

## 品質チェックとカリキュラム

- Day 1の完成レッスン: `lesson.html?day=1&v=4`
- 公開済みレッスンのみの一覧: `curriculum.json`
- 新しいDayは公開のたびに一覧へ追加。終了日や総日数は固定しません。
- 日次生成・検証処理: `scripts/generate_daily_lesson.py`
- 日次処理のログ: GitHub Actions の workflow run
- Day 1の進捗記録: このブラウザ内に保存（他の端末とは同期しません）

まだ公開されていないDayはトップページに表示しません。自動生成Pull Requestの内容を確認して `main` へマージすると、そのDayが `curriculum.json` に加わり、トップページにも表示されます。
