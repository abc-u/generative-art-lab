# Generative Art Lab

日本語で、ジェネラティブアートの考え方を見て・動かして・つくりながら学ぶ静的サイトです。GitHub Pages の `main` / `/(root)` から配信できます。外部ビルドやJavaScriptライブラリは使いません。

## 公開

- Repository: https://github.com/abc-u/generative-art-lab
- URL: https://abc-u.github.io/generative-art-lab/
- Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/(root)`

`index.html`、`lesson.html`、`styles.css`、`app.js` がサイト共通部分です。トップページにはシードを変えて見比べるスタディギャラリーがあります。Dayごとの教材データは `lessons/day-NN.json`、カリキュラム一覧は `curriculum.json` に置きます。Day 1の詳細ページとデモは `lesson.html` / `lesson.js` に含まれます。各Dayは共通テンプレートから表示され、完了状況はブラウザの localStorage に保存されます。

## 日次レッスンの運用

毎朝 08:57 JST に Claude の定期タスクが起動し、`curriculum.json` の次の未公開 Day を1つ教材にします。流れは次のとおりです。

1. 次の `planned` の Day を選ぶ。残りがなければ、学びのつながりに沿って計画を書き足す（固定の日数や上限は設けない）。
2. 作家・作品の参照先と、作品画像のライセンス（Wikimedia Commons）を実際に確認する。
3. `lessons/day-NN.json` を書き、`curriculum.json` の該当 Day を `published` にする。
4. 次の2つのチェックを両方通す。
   - `python3 scripts/validate_lesson.py lessons/day-NN.json` — 項目の過不足、Day 順と重複、コードとデモの構文、外部通信の禁止、参照 URL と画像ライセンスの確認
   - `node scripts/check_lesson_render.mjs NN` — PC 幅とスマホ幅で開き、スクリプトエラー、横スクロール、デモの描画を確認
5. 通過したら `main` に直接コミットして公開する。通過しなかった場合は公開せず、`automation/day-NN` ブランチの Pull Request にして理由を書く。

同じ日に2つ公開しないよう、その日の公開コミットがすでにあれば何もしません。`main` への push ごとに GitHub Actions の **Lesson checks** が全レッスンを再検証します。

制作ルール（教材の基準、作品画像の扱い、デザイン方針）はリポジトリの外で管理し、定期タスクの指示に含めています。ルールを変えたときは定期タスクの指示も更新してください。

## 品質チェックとカリキュラム

- Day 1の完成レッスン: `lesson.html?day=1&v=2`
- 学習計画と公開状態: `curriculum.json`（レッスン数は固定しない）
- 教材データの検証: `scripts/validate_lesson.py`（`--all` で公開済み全件）
- 表示確認: `scripts/check_lesson_render.mjs`（Playwright と Chromium が必要）
- 進捗記録: このブラウザ内に保存（他の端末とは同期しません）
