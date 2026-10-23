#!/usr/bin/env python3
"""Generate and validate the next curriculum lesson for a review PR."""
import html.parser
import json
import os
import re
import subprocess
import sys
import urllib.error
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
        "experiments": {"type": "array", "minItems": 4, "maxItems": 6, "items": {"type":"object","additionalProperties":False,"required":["title","action","observe"],"properties":{"title":{"type":"string"},"action":{"type":"string","minLength":30},"observe":{"type":"string","minLength":30}}}},
        "artist": {"type":"object","additionalProperties":False,"required":["name","work","context","relation","references"],"properties":{"name":{"type":"string"},"work":{"type":"string"},"context":{"type":"string","minLength":80},"relation":{"type":"string","minLength":60},"references":{"type":"array","minItems":1,"maxItems":2,"items":{"type":"object","additionalProperties":False,"required":["source","label","url"],"properties":{"source":{"type":"string"},"label":{"type":"string"},"url":{"type":"string","pattern":"^https://"}}}}}},
        "extension": {"type":"object","additionalProperties":False,"required":["keywords","next"],"properties":{"keywords":{"type":"array","minItems":3,"maxItems":6,"items":{"type":"string"}},"next":{"type":"string","minLength":40}}}
    }
}

class DemoParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]; self.external=[]; self.scripts=0; self.canvas=0; self.controls=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs); self.tags.append(tag)
        if tag in {"canvas"}: self.canvas += 1
        if tag in {"input","button","select"}: self.controls += 1
        if tag == "script": self.scripts += 1
        if tag in {"iframe","object","embed","form","link","base"}: self.external.append(tag)
        if any(k.lower().startswith("on") for k in attrs): self.external.append("inline event attribute")
        if tag in {"script","img","audio","video","source"} and attrs.get("src"): self.external.append("external asset")

def fail(message):
    raise SystemExit(f"Lesson validation failed: {message}")

def next_day(data):
    published = {item["day"] for item in data["lessons"] if item["status"] == "published"}
    if published != set(range(1, max(published, default=0) + 1)):
        fail("published days are not consecutive")
    for item in data["lessons"]:
        if item["status"] == "planned": return item
    fail("curriculum has no remaining planned lessons")

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
    if lesson["phase"] != planned["phase"]: fail("phase does not match the curriculum plan")
    if lesson["title"].strip().casefold() in existing_titles: fail("duplicate lesson title")
    for url in [x["url"] for x in lesson["artist"]["references"]]:
        if not url.startswith("https://") or any(c in url for c in "<>\"'"): fail("invalid reference URL")
        request=urllib.request.Request(url,headers={"User-Agent":"GenerativeArtLab-content-check/1.0"})
        try:
            with urllib.request.urlopen(request,timeout=20) as response:
                if response.status >= 400: fail(f"reference returned HTTP {response.status}: {url}")
        except (urllib.error.URLError,TimeoutError) as error:
            fail(f"reference could not be verified: {url} ({error})")
    code=lesson["code"]
    if re.search(r"<\s*script|javascript:",code,re.I): fail("unsafe code sample")
    check=subprocess.run(["node","--check"],input=("function lesson(){\n"+code+"\n}\n").encode(),capture_output=True)
    if check.returncode: fail("code sample has a syntax error: "+check.stderr.decode(errors="replace")[:500])
    parser=DemoParser(); parser.feed(lesson["demo"]["html"])
    if parser.external: fail("demo contains a forbidden external or active element: "+", ".join(parser.external))
    if parser.canvas < 1 or parser.controls < 1 or parser.scripts < 1: fail("demo needs a canvas, an interactive control, and inline JavaScript")
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
講座の次回は Day {day}: {planned['title']}。テーマ: {planned['topic']}。学習計画: {planned['description']}。Phase: {planned['phase']}。
同じ講座で公開済みのタイトル: {', '.join(x['title'] for x in data['lessons'] if x['status']=='published')}。
必須方針: 15〜20分の日本語教材。数学が苦手な人向けに、日常のたとえ→文章で説明する図解→具体的な数値を一段ずつ計算→必要最小限のコードの順にする。全変数と式の記号を説明する。実験は初期観察→一つの値→極端な値→組み合わせ→コード改造の段階を含み、観察理由も書く。
デモは自己完結のHTML文字列。HTML内にcanvasと操作可能なinput/button/selectを含め、アルゴリズムに関係する操作と日本語のラベルを実装する。CSSとJavaScriptはインラインにし、外部ライブラリ、外部通信、画像素材、埋め込みiframe、イベント属性は禁止。スマートフォン対応、再生成、初期化、PNG保存をできる範囲で含める。デモの説明は本文の用語と数値例に対応させる。
作家は実在の作家・確認可能な具体的作品を選ぶ。実際の手法が確認できない場合は表現上の類似と明記する。参考URLは美術館・作家・公的機関などの確認できるページのみ。未確認の作品情報やURLを作らず、不確かな場合は確実に知る作品に差し替える。参考文献リンクは必ず https URL。
JSON以外は返さない。titleは上記の計画から逸脱させない。既存公開教材に重複するアルゴリズムは避ける。"""
    lesson=get_response(prompt); validate(lesson,planned,titles)
    lesson.update({"day":day,"status":"published"})
    path.write_text(json.dumps(lesson,ensure_ascii=False,indent=2)+"\n")
    planned["status"]="published"; planned["title"]=lesson["title"]; planned["topic"]=lesson["topic"]; planned["description"]=lesson["subtitle"]
    CURRICULUM.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print(f"Generated and validated Day {day}: {lesson['title']}")

if __name__=="__main__": main()
