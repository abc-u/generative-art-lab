#!/usr/bin/env python3
"""Generate and validate the next curriculum lesson for a review PR."""
import html.parser
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / "curriculum.json"
LESSONS = ROOT / "lessons"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "subtitle", "topic", "phase", "minutes", "level", "algorithm", "applications", "prerequisites", "connection", "intuition", "numbers", "code", "demo", "experiments", "artist", "extension"],
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 80},
        "subtitle": {"type": "string", "minLength": 5, "maxLength": 140},
        "topic": {"type": "string", "minLength": 2, "maxLength": 40},
        "phase": {"type": "integer", "minimum": 1, "maximum": 4},
        "minutes": {"type": "integer", "minimum": 15, "maximum": 20},
        "level": {"type": "string", "minLength": 2, "maxLength": 20},
        "algorithm": {"type": "string", "minLength": 120},
        "applications": {"type": "string", "minLength": 40},
        "prerequisites": {"type": "string", "minLength": 30},
        "connection": {"type": "string", "minLength": 40},
        "intuition": {"type": "object", "additionalProperties": False, "required": ["title", "story", "visual", "diagram"], "properties": {"title":{"type":"string"},"story":{"type":"string","minLength":100},"visual":{"type":"string","minLength":20},"diagram":{"type":"string","minLength":20}}},
        "numbers": {"type": "object", "additionalProperties": False, "required": ["setup", "steps", "note"], "properties": {"setup":{"type":"string","minLength":50},"steps":{"type":"array","minItems":3,"maxItems":6,"items":{"type":"object","additionalProperties":False,"required":["label","calculation"],"properties":{"label":{"type":"string"},"calculation":{"type":"string"}}}},"note":{"type":"string","minLength":40}}},
        "code": {"type": "string", "minLength": 40},
        "demo": {"type": "object", "additionalProperties": False, "required": ["title", "caption", "html"], "properties": {"title":{"type":"string","minLength":3},"caption":{"type":"string","minLength":20},"html":{"type":"string","minLength":500}}},
        "experiments": {"type": "array", "minItems": 4, "maxItems": 6, "items": {"type":"object","additionalProperties":False,"required":["title","action","observe","demoState"],"properties":{"title":{"type":"string"},"action":{"type":"string","minLength":30},"observe":{"type":"string","minLength":30},"demoState":{"type":"array","minItems":1,"maxItems":4,"items":{"type":"object","additionalProperties":False,"required":["selector","value"],"properties":{"selector":{"type":"string","pattern":"^#[A-Za-z][A-Za-z0-9_-]*$"},"value":{"type":"string","minLength":1,"maxLength":32}}}}}}},
        "artist": {"type":"object","additionalProperties":False,"required":["name","work","context","relation","references","image"],"properties":{"name":{"type":"string"},"work":{"type":"string"},"context":{"type":"string","minLength":80},"relation":{"type":"string","minLength":60},"references":{"type":"array","minItems":1,"maxItems":2,"items":{"type":"object","additionalProperties":False,"required":["source","label","url"],"properties":{"source":{"type":"string"},"label":{"type":"string"},"url":{"type":"string","pattern":"^https://"}}}},"image":{"anyOf":[{"type":"null"},{"type":"object","additionalProperties":False,"required":["url","alt","sourceUrl","license","credit"],"properties":{"url":{"type":"string","pattern":"^https://"},"alt":{"type":"string","minLength":20},"sourceUrl":{"type":"string","pattern":"^https://"},"license":{"type":"string","enum":["CC0 1.0","Public Domain","CC BY 4.0","CC BY-SA 4.0"]},"credit":{"type":"string","minLength":3}}}]}}},
        "extension": {"type":"object","additionalProperties":False,"required":["keywords","next"],"properties":{"keywords":{"type":"array","minItems":3,"maxItems":6,"items":{"type":"string"}},"next":{"type":"string","minLength":40}}}
    }
}

class DemoParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]; self.ids=set(); self.control_ids=set(); self.external=[]; self.scripts=0; self.canvas=0; self.controls=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs); self.tags.append(tag)
        if attrs.get("id"): self.ids.add(attrs["id"])
        if tag in {"canvas"}: self.canvas += 1
        if tag in {"input","button","select"}:
            self.controls += 1
            if attrs.get("id"): self.control_ids.add(attrs["id"])
        if tag == "script": self.scripts += 1
        if tag in {"iframe","object","embed","form","link","base"}: self.external.append(tag)
        if any(k.lower().startswith("on") for k in attrs): self.external.append("inline event attribute")
        if tag in {"script","img","audio","video","source"} and attrs.get("src"): self.external.append("external asset")

def fail(message):
    raise SystemExit(f"Lesson validation failed: {message}")

def next_day(data):
    published=sorted(item["day"] for item in data["lessons"] if item["status"]=="published")
    if published != list(range(1,max(published,default=0)+1)):
        fail("published days are not consecutive")
    return {"day":max(published,default=0)+1}

def get_response(prompt):
    payload={"model":MODEL,"input":[{"role":"user","content":[{"type":"input_text","text":prompt}]}],"text":{"format":{"type":"json_schema","name":"generative_art_lesson","strict":True,"schema":SCHEMA}},"max_output_tokens":12000}
    request=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {os.environ['OPENAI_API_KEY']}","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(request,timeout=180) as response: result=json.loads(response.read())
    except urllib.error.HTTPError as error:
        fail(f"OpenAI API returned HTTP {error.code}: {error.read().decode(errors='replace')[:500]}")
    for output in result.get("output",[]):
        for part in output.get("content",[]):
            if part.get("type")=="output_text": return json.loads(part["text"])
    fail("Responses API returned no structured output")

def validate(lesson, planned, existing_titles):
    if lesson["title"].strip().casefold() in existing_titles: fail("duplicate lesson title")
    reference_pages={}
    for url in [x["url"] for x in lesson["artist"]["references"]]:
        if not url.startswith("https://") or any(c in url for c in "<>\"'"): fail("invalid reference URL")
        request=urllib.request.Request(url,headers={"User-Agent":"GenerativeArtLab-content-check/1.0"})
        try:
            with urllib.request.urlopen(request,timeout=20) as response:
                if response.status >= 400: fail(f"reference returned HTTP {response.status}: {url}")
                reference_pages[url]=response.read(2_000_000).decode(errors="replace")
        except (urllib.error.URLError,TimeoutError) as error:
            fail(f"reference could not be verified: {url} ({error})")
    image=lesson["artist"]["image"]
    if image is not None:
        if image["sourceUrl"] not in [x["url"] for x in lesson["artist"]["references"]]: fail("image source must also appear in artist references")
        if urllib.parse.urlparse(image["url"]).hostname != "upload.wikimedia.org": fail("artist images must be hosted on Wikimedia Commons")
        if urllib.parse.urlparse(image["sourceUrl"]).hostname != "commons.wikimedia.org": fail("image license source must be a Wikimedia Commons file page")
        if image["license"] not in {"CC0 1.0","Public Domain","CC BY 4.0","CC BY-SA 4.0"}: fail("artist image license is not on the allowed list")
        source_text=reference_pages.get(image["sourceUrl"],"").lower()
        if image["license"].lower() not in source_text: fail("image source page does not confirm the declared license")
        request=urllib.request.Request(image["url"],method="HEAD",headers={"User-Agent":"GenerativeArtLab-content-check/1.0"})
        try:
            with urllib.request.urlopen(request,timeout=20) as response:
                if not response.headers.get("Content-Type","").lower().startswith("image/"): fail("artist image URL is not served as an image")
        except (urllib.error.URLError,TimeoutError) as error:
            fail(f"artist image could not be verified: {image['url']} ({error})")
    code=lesson["code"]
    if re.search(r"<\s*script|javascript:",code,re.I): fail("unsafe code sample")
    check=subprocess.run(["node","--check"],input=("function lesson(){\n"+code+"\n}\n").encode(),capture_output=True)
    if check.returncode: fail("code sample has a syntax error: "+check.stderr.decode(errors="replace")[:500])
    parser=DemoParser(); parser.feed(lesson["demo"]["html"])
    if parser.external: fail("demo contains a forbidden external or active element: "+", ".join(parser.external))
    if parser.canvas < 1 or parser.controls < 1 or parser.scripts < 1: fail("demo needs a canvas, an interactive control, and inline JavaScript")
    if "gal-experiment" not in lesson["demo"]["html"] or "dispatchEvent" not in lesson["demo"]["html"] or not re.search(r"addEventListener\s*\(\s*['\"]message", lesson["demo"]["html"]): fail("demo needs the experiment message bridge")
    for index, experiment in enumerate(lesson["experiments"], start=1):
        for control in experiment["demoState"]:
            if control["selector"][1:] not in parser.control_ids: fail(f"experiment {index} references missing input/select {control['selector']}")
    scripts=re.findall(r"<script\b[^>]*>(.*?)</script\s*>",lesson["demo"]["html"],re.I|re.S)
    for script in scripts:
        check=subprocess.run(["node","--check"],input=script.encode(),capture_output=True)
        if check.returncode: fail("demo JavaScript has a syntax error: "+check.stderr.decode(errors="replace")[:500])
    if re.search(r"\b(fetch|XMLHttpRequest|WebSocket|importScripts)\s*\(",lesson["demo"]["html"]): fail("demo must not make network requests")
    if not any("." in reference["url"].split("/")[2] for reference in lesson["artist"]["references"]): fail("artist reference URL appears invalid")

def main():
    if not os.environ.get("OPENAI_API_KEY"): fail("OPENAI_API_KEY secret is required")
    data=json.loads(CURRICULUM.read_text())
    planned=next_day(data); day=planned["day"]; path=LESSONS/f"day-{day:02}.json"
    if path.exists(): fail(f"refusing to overwrite existing lesson: {path.name}")
    titles={x["title"].strip().casefold() for x in data["lessons"] if x["status"]=="published"}
    prompt=f"""あなたは日本語のジェネラティブアート初心者講座の編集者です。次の1レッスンをJSON Schemaどおりに作成してください。
講座の次は Day {day} です。Day数に上限や固定の終了日を設けず、公開済みの内容から自然につながる新しい概念を1つ選んでください。テーマ案: 格子・座標・反復・条件・確率・色・波・ノイズ・流れ・粒子・フラクタル・セルオートマトン・群れ・空間分割・曲線・色空間・画像表現・最適化・インタラクション・作品制作。これらは例であり、順番・区切り・最終Dayを固定しません。Phaseは1〜4の広い学習領域から、内容に合わせて選んでください。
公開済みレッスン（Day・タイトル・テーマ）: {', '.join(f"Day {x['day']} {x['title']}（{x['topic']}）" for x in data['lessons'])}。直前のレッスンとのつながりを明確にし、既習テーマをそのまま繰り返さないでください。
同じ講座で公開済みのタイトル: {', '.join(x['title'] for x in data['lessons'] if x['status']=='published')}。
必須方針: 15〜20分の日本語教材。数学が苦手な人向けに、日常のたとえ→文章で説明する図解→具体的な数値を一段ずつ計算→必要最小限のコードの順にする。全変数と式の記号を説明する。実験は初期観察→一つの値→極端な値→組み合わせ→コード改造の段階を含み、観察理由も書く。
デモは自己完結のHTML文字列。HTML内にcanvasと操作可能なinput/button/selectを含め、アルゴリズムに関係する操作と日本語のラベルを実装する。CSSとJavaScriptはインラインにし、外部ライブラリ、外部通信、画像素材、埋め込みiframe、イベント属性は禁止。スマートフォン対応、再生成、初期化、PNG保存をできる範囲で含める。デモの説明は本文の用語と数値例に対応させる。各実験にはdemoStateを含め、デモ内にあるinputまたはselectのCSS IDセレクタと変更後の文字列値を1〜4組指定する。デモのJavaScriptには、親ページから届く type="gal-experiment" のmessageを受け取り、指定されたコントロールへ値を反映し、input/changeイベントを発火してキャンバスを更新するリスナーを実装する。
作家は実在の作家・確認可能な具体的作品を選ぶ。実際の手法が確認できない場合は表現上の類似と明記する。参考URLは美術館・作家・公的機関などの確認できるページのみ。未確認の作品情報やURLを作らず、不確かな場合は確実に知る作品に差し替える。参考文献リンクは必ず https URL。
作家作品の画像は、Wikimedia Commons上でCC0 1.0、Public Domain、CC BY 4.0、CC BY-SA 4.0のいずれかと確認できる場合だけ含める。image.urlはupload.wikimedia.org上の直接画像URL、image.sourceUrlは同じ作品のcommons.wikimedia.orgのファイルページとし、sourceUrlもreferencesに含める。altは作品の内容を説明し、creditには必要な作者名などを記す。権利やライセンスを確実に確認できない場合はimageをnullにする（画像なしでも作品と公式資料へのリンクは必ず紹介する）。
JSON以外は返さない。タイトルは今回選んだ新しい概念を短く表す。既存公開教材に重複するアルゴリズムは避ける。"""
    lesson=get_response(prompt); validate(lesson,planned,titles)
    lesson.update({"day":day,"status":"published"})
    path.write_text(json.dumps(lesson,ensure_ascii=False,indent=2)+"\n")
    data["lessons"].append({"day":day,"title":lesson["title"],"topic":lesson["topic"],"description":lesson["subtitle"],"phase":lesson["phase"],"status":"published"})
    CURRICULUM.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print(f"Generated and validated Day {day}: {lesson['title']}")

if __name__=="__main__": main()
