const params = new URLSearchParams(location.search);
const dayNumber = Math.max(1, Number(params.get("day")) || 1);
const $ = (selector) => document.querySelector(selector);
const pad = (n) => String(n).padStart(2, "0");

// localStorage can be unavailable (private mode, blocked storage); progress then lasts for the visit only.
const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* keep going without saving */ } },
};

function setupProgress(day, totalSteps) {
  const doneKey = `gal-day-${pad(day)}-complete`;
  const triedKey = `gal-day-${pad(day)}-tried`;
  let tried;
  try { tried = new Set(JSON.parse(store.get(triedKey) || "[]")); } catch { tried = new Set(); }
  const button = $("#mark-complete");
  const sync = () => {
    const done = store.get(doneKey) === "true";
    $("#progress-fill").style.width = done ? "100%" : `${Math.round((tried.size / totalSteps) * 90)}%`;
    $("#progress-label").textContent = done ? `YOUR PROGRESS · DAY ${pad(day)} DONE` : `YOUR PROGRESS · EXPERIMENTS ${tried.size} / ${totalSteps}`;
    $("#progress-note").textContent = done ? "おつかれさまでした。完了の記録はこのブラウザに保存されます。" : `${totalSteps}つの実験を試したら、レッスンを完了にしましょう。`;
    const status = $("#lesson-status");
    status.textContent = done ? "完了" : tried.size ? `実験中 ${tried.size}/${totalSteps}` : "未完了";
    status.classList.toggle("is-done", done);
    button.textContent = done ? "完了を取り消す ↺" : "このレッスンを完了 ✓";
    button.classList.toggle("done", done);
    button.setAttribute("aria-pressed", String(done));
    document.querySelectorAll("#experiment-list > li").forEach((item, index) => {
      const on = tried.has(index + 1);
      item.classList.toggle("is-tried", on);
      item.querySelector(".step-badge").textContent = on ? "✓" : pad(index + 1);
    });
  };
  const save = () => store.set(triedKey, JSON.stringify([...tried]));
  button.addEventListener("click", () => { store.set(doneKey, String(store.get(doneKey) !== "true")); sync(); });
  sync();
  return {
    mark(step) { tried.add(step); save(); sync(); },
    toggle(step) { if (tried.has(step)) tried.delete(step); else tried.add(step); save(); sync(); return tried.has(step); },
  };
}

async function setupNextLesson(day) {
  try {
    const curriculum = await (await fetch("./curriculum.json")).json();
    const next = curriculum.lessons.find((lesson) => lesson.day === day + 1);
    const link = $("#next-lesson");
    if (!next) {
      $("#next-meta").textContent = "NEXT";
      $("#next-title").textContent = "次のレッスンを準備しています";
      $("#next-desc").textContent = "新しいレッスンは毎日ひとつずつ追加されます。";
      $("#next-go").textContent = "カリキュラムへ";
      return;
    }
    const open = next.status === "published";
    $("#next-meta").textContent = `NEXT · DAY ${pad(next.day)}${open ? "" : " · PLANNED"}`;
    $("#next-title").textContent = next.title;
    $("#next-desc").textContent = next.description;
    $("#next-go").textContent = open ? "レッスンを開く →" : "準備中";
    link.classList.toggle("is-open", open);
    link.href = open ? `./lesson.html?day=${next.day}` : "./#curriculum";
    const cta = $(".nav-cta");
    if (cta && open) cta.href = link.href;
  } catch { /* the card keeps its default text */ }
}

/* ---------- Day 1: the grid playground ---------- */

const palettes = {
  clay: { name: "Clay / Moss", bg: "#e8dfcc", ink: "#32352e", accent: "#cf6445", second: "#596a54" },
  ink: { name: "Ink / Paper", bg: "#e9e7df", ink: "#202326", accent: "#c34535", second: "#707779" },
  citrus: { name: "Citrus / Plum", bg: "#e9e1cf", ink: "#402d47", accent: "#e9893d", second: "#93a23e" },
  ocean: { name: "Ocean / Sand", bg: "#e6dfcf", ink: "#244651", accent: "#347a91", second: "#c16c4e" },
};
const shapeNames = { square: "四角形", circle: "円", diamond: "ひし形", line: "線" };
const initial = { cols: 12, rows: 12, size: 58, shape: "square", chance: 0, palette: "clay", seed: 42 };

function seededRandom(seed) {
  return () => {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function describe(chance) {
  if (chance === 0) return "いまは規則的な格子です。";
  if (chance < 35) return "小さなゆらぎが規則に表情を加えています。";
  if (chance < 75) return "規則の骨組みを残しながら、大きく揺れています。";
  return "ゆらぎが強く、図形が自由に動いています。";
}

function paintGrid(canvas, state) {
  const box = canvas.getBoundingClientRect();
  if (!box.width) return;
  const dpr = Math.min(devicePixelRatio || 1, 2);
  const width = Math.round(box.width * dpr), height = Math.round(box.height * dpr);
  if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  const w = box.width, h = box.height, palette = palettes[state.palette];
  const cell = w / state.cols, gap = h / state.rows, scale = state.size / 100, chance = state.chance / 100;
  const random = seededRandom(state.seed);
  context.fillStyle = palette.bg;
  context.fillRect(0, 0, w, h);
  for (let row = 0; row < state.rows; row++) {
    for (let col = 0; col < state.cols; col++) {
      const jitter = chance * 0.45;
      const dx = (random() - 0.5) * cell * jitter, dy = (random() - 0.5) * gap * jitter;
      const angle = (random() - 0.5) * chance * 0.72;
      const s = Math.min(cell, gap) * scale * (1 + (random() - 0.5) * chance * 0.2);
      context.save();
      context.translate(col * cell + cell / 2 + dx, row * gap + gap / 2 + dy);
      context.rotate(angle);
      context.fillStyle = (row + col) % 7 === 0 ? palette.accent : (row * 3 + col) % 5 === 0 ? palette.second : palette.ink;
      context.strokeStyle = context.fillStyle;
      context.lineWidth = Math.max(1.2, s * 0.08);
      const half = s / 2;
      context.beginPath();
      if (state.shape === "circle") { context.arc(0, 0, half, 0, Math.PI * 2); context.fill(); }
      else if (state.shape === "diamond") { context.moveTo(0, -half); context.lineTo(half, 0); context.lineTo(0, half); context.lineTo(-half, 0); context.closePath(); context.fill(); }
      else if (state.shape === "line") { context.moveTo(-half, 0); context.lineTo(half, 0); context.stroke(); }
      else context.fillRect(-half, -half, s, s);
      context.restore();
    }
  }
}

function setupPlayground() {
  let state = { ...initial };
  const main = $("#grid-demo"), mirror = $("#grid-mirror");
  const ranges = ["cols", "rows", "size", "chance", "seed"];
  const units = { cols: " 列", rows: " 行", size: "%", chance: "%", seed: "" };
  const outputs = { cols: "#cols-out", rows: "#rows-out", size: "#size-out", chance: "#chance-out", seed: "#seed-input-out" };
  const progress = setupProgress(1, document.querySelectorAll("#experiment-list > li").length);

  function render() {
    paintGrid(main, state);
    paintGrid(mirror, state);
    for (const key of ranges) {
      $(`#${key}`).value = state[key];
      $(outputs[key]).textContent = `${state[key]}${units[key]}`;
    }
    document.querySelectorAll("[data-shape]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.shape === state.shape)));
    document.querySelectorAll("[data-palette]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.palette === state.palette)));
    const seedLabel = pad(state.seed).padStart(3, "0");
    $("#seed-value").textContent = seedLabel;
    $("#palette-name").textContent = palettes[state.palette].name;
    $("#shape-name").textContent = shapeNames[state.shape];
    $("#chance-readout").textContent = `${state.chance}%`;
    $("#live-description").textContent = describe(state.chance);
    $("#mirror-meta").textContent = `ゆらぎ ${state.chance}% · SEED ${seedLabel}`;
    $("#mirror-description").textContent = describe(state.chance);
  }
  const update = (patch) => { state = { ...state, ...patch }; render(); };
  const randomSeed = () => 1 + Math.floor(Math.random() * 999);

  ranges.forEach((key) => $(`#${key}`).addEventListener("input", (event) => update({ [key]: Number(event.target.value) })));
  document.querySelectorAll("[data-shape]").forEach((button) => button.addEventListener("click", () => update({ shape: button.dataset.shape })));
  document.querySelectorAll("[data-palette]").forEach((button) => button.addEventListener("click", () => update({ palette: button.dataset.palette })));
  $("#shuffle-seed").addEventListener("click", () => update({ seed: randomSeed() }));
  $("#reset-controls").addEventListener("click", () => update({ ...initial }));
  $("#save-png").addEventListener("click", () => {
    const link = document.createElement("a");
    link.download = `generative-art-day01-seed-${state.seed}.png`;
    link.href = main.toDataURL("image/png");
    link.click();
  });
  document.querySelectorAll(".try-button").forEach((button) => button.addEventListener("click", () => {
    const patch = JSON.parse(button.dataset.patch);
    if (patch.seed === "random") patch.seed = randomSeed();
    update(patch);
    progress.mark(Number(button.dataset.step));
    // On narrow screens the preview sits above the steps, so bring it into view.
    if (matchMedia("(max-width: 900px)").matches) mirror.scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  const observer = new ResizeObserver(render);
  observer.observe(main);
  observer.observe(mirror);
  render();
}

/* ---------- Day 2+: lessons stored as JSON ---------- */

function escapeLessonText(text) { return String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll("\"", "&quot;").replaceAll("'", "&#39;"); }
function escapeLessonData(value, key = "") {
  if (typeof value === "string") return key === "html" ? value : escapeLessonText(value);
  if (Array.isArray(value)) return value.map((item) => escapeLessonData(item));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([childKey, child]) => [childKey, escapeLessonData(child, childKey)]));
  return value;
}

function renderGeneratedLesson(day, lesson) {
  document.title = `Day ${day} — ${lesson.title.replaceAll("&amp;", "&")} | Generative Art Lab`;
  $("#crumb-day").textContent = `DAY ${pad(day)}`;
  $("#lesson-eyebrow").innerHTML = `DAY ${pad(day)} <span class="heading-separator">/</span> PHASE ${pad(lesson.phase)} · ${lesson.topic}`;
  $("#lesson-title").innerHTML = lesson.title;
  // Japanese titles are long at the Latin display size; step them down so they stay on one or two lines.
  $("#lesson-title").classList.toggle("is-long", /[^\x00-\x7F]/.test(lesson.title) || lesson.title.length > 18);
  $("#lesson-subtitle").innerHTML = lesson.subtitle;
  $("#fact-time").textContent = `約${lesson.minutes}分`;
  $("#fact-level").innerHTML = lesson.level;
  $("#lesson-flow").innerHTML = [["goal", "今日の目標"], ["intuition", "直感でつかむ"], ["numbers", "数字で追う"], ["experiment", "実験してみよう"], ["artist", "作品を見てみる"], ["next", "次につながること"]]
    .map(([id, label], index) => `<a href="#${id}"><span>${pad(index + 1)}</span>${label}</a>`).join("");

  $("#playground").innerHTML = `<div class="demo-topline"><div><p class="eyebrow">THE PLAYGROUND · LIVE CANVAS</p><h2 id="demo-title">${lesson.demo.title}</h2></div></div><div class="generated-demo-frame"><iframe title="${lesson.demo.title}" sandbox="allow-scripts allow-downloads"></iframe></div><p class="demo-caption">${lesson.demo.caption}</p>`;
  // The demo runs in a sandboxed frame with its own CSP so it cannot reach the network or the page.
  // The frame cannot be measured from outside the sandbox, so the demo reports its own height.
  const reportHeight = `<script>(()=>{const send=()=>{const b=document.body;if(!b)return;const m=getComputedStyle(b);parent.postMessage({galDemoHeight:Math.ceil(b.getBoundingClientRect().height+parseFloat(m.marginTop)+parseFloat(m.marginBottom))},"*")};addEventListener("load",()=>{send();new ResizeObserver(send).observe(document.body)});})();<\/script>`;
  const frame = $("#playground iframe");
  frame.srcdoc = lesson.demo.html
    .replace(/<head([^>]*)>/i, `<head$1><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; font-src 'none'; form-action 'none'">`)
    .replace(/<\/body>/i, (end) => reportHeight + end);
  addEventListener("message", (event) => {
    const height = Number(event.data?.galDemoHeight);
    if (event.source === frame.contentWindow && height > 0) frame.parentElement.style.height = `${Math.min(Math.max(height, 200), 1400)}px`;
  });

  $("#article-intro").innerHTML = `<section class="article-section" id="goal"><p class="eyebrow">01 · TODAY'S ALGORITHM</p><h2>今日のアルゴリズム</h2><p>${lesson.algorithm}</p><div class="fact-grid">${[["何ができる？", lesson.applications], ["前提知識", lesson.prerequisites], ["前回とのつながり", lesson.connection]].map(([label, text]) => `<div><span>${label}</span><p>${text}</p></div>`).join("")}</div></section>`
    + `<section class="article-section" id="intuition"><p class="eyebrow">02 · FIRST, AN EVERYDAY IMAGE</p><h2>${lesson.intuition.title}</h2><p>${lesson.intuition.story}</p><div class="rule-card"><span class="rule-index">VISUAL IDEA</span><p>${lesson.intuition.visual}</p><span>${lesson.intuition.diagram}</span></div></section>`
    + `<section class="article-section" id="numbers"><p class="eyebrow">03 · A SMALL NUMBER EXAMPLE</p><h2>数字で追ってみる。</h2><p>${lesson.numbers.setup}</p><div class="math-card"><div class="math-steps">${lesson.numbers.steps.map((step) => `<div><span>${step.label}</span><code>${step.calculation}</code></div>`).join("")}</div><div class="math-note">${lesson.numbers.note}</div></div><div class="code-card"><div class="code-head"><span>HOW THE RULE BECOMES CODE</span><span>JavaScript</span></div><pre><code>${lesson.code}</code></pre></div></section>`;

  $("#experiment-lead").textContent = "上のデモで、ひとつずつ変化を加えましょう。試したら「やってみた」を押すと、進み具合に記録されます。";
  $("#experiment").classList.add("no-preview");
  $(".experiment-preview")?.remove();
  $("#experiment .observation")?.remove();
  $("#experiment-list").innerHTML = lesson.experiments.map((step, index) => `<li><span class="step-badge">${pad(index + 1)}</span><div><b>${step.title}</b><p>${step.action} ${step.observe}</p><button type="button" class="try-button" data-step="${index + 1}" aria-pressed="false">やってみた</button></div></li>`).join("");

  const artist = lesson.artist;
  const image = artist.image ? `<figure class="artist-work"><a href="${artist.image.sourceUrl}" target="_blank" rel="noreferrer"><img src="${artist.image.url}" alt="${artist.image.alt}" loading="lazy" decoding="async" referrerpolicy="no-referrer"></a><figcaption><strong>${artist.name}, <i>${artist.work}</i></strong><span>${artist.image.credit} · ${artist.image.license}</span><a href="${artist.image.sourceUrl}" target="_blank" rel="noreferrer">作品画像の出典 ↗</a></figcaption></figure>` : "";
  $("#article-outro").innerHTML = `<section class="article-section" id="artist"><p class="eyebrow">05 · ARTIST &amp; WORK</p><h2>${artist.name} — <i>${artist.work}</i></h2><p>${artist.context}</p><p>${artist.relation}</p>${image}<div class="artist-links">${artist.references.map((ref) => `<a href="${ref.url}" target="_blank" rel="noreferrer"><span>${ref.source}</span><b>${ref.label} ↗</b></a>`).join("")}</div></section>`
    + `<section class="article-section" id="next"><p class="eyebrow">06 · KEEP EXPLORING</p><h2>次につながること。</h2><p>${lesson.extension.next}</p><div class="next-links"><div><span>検索キーワード</span><p>${lesson.extension.keywords.join(" / ")}</p></div></div></section>`;

  const progress = setupProgress(day, lesson.experiments.length);
  document.querySelectorAll(".try-button").forEach((button) => {
    const step = Number(button.dataset.step);
    const label = (on) => { button.textContent = on ? "やってみた ✓" : "やってみた"; button.setAttribute("aria-pressed", String(on)); };
    label(button.closest("li").classList.contains("is-tried"));
    button.addEventListener("click", () => label(progress.toggle(step)));
  });
}

function showMissingLesson() {
  for (const selector of [".lesson-hero", "#lesson-flow", "#article-intro", "#experiment", "#article-outro", "#finish"]) $(selector)?.remove();
  $("#crumb-day").textContent = `DAY ${pad(dayNumber)}`;
  $("#playground").innerHTML = '<p class="missing-lesson">このDayのレッスンはまだ公開されていません。<a href="./#curriculum">カリキュラムに戻る ↗</a></p>';
}

async function loadGeneratedLesson(day) {
  try {
    const response = await fetch(`./lessons/day-${pad(day)}.json`);
    if (!response.ok) throw new Error("lesson not published");
    renderGeneratedLesson(day, escapeLessonData(await response.json()));
  } catch {
    showMissingLesson();
  }
}

if (dayNumber === 1) setupPlayground();
else loadGeneratedLesson(dayNumber);
setupNextLesson(dayNumber);
