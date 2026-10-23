#!/usr/bin/env python3
"""Validate lesson data before it is published.

Usage:
  python3 scripts/validate_lesson.py lessons/day-02.json   # one lesson + curriculum consistency
  python3 scripts/validate_lesson.py --all                 # every published lesson
  add --offline to skip checks that fetch reference pages and images.

Exits non-zero with a list of problems when anything fails.
"""
import argparse
import html.parser
import json
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
ALLOWED_LICENSES = ["CC0 1.0", "Public Domain", "CC BY 4.0", "CC BY-SA 4.0"]
USER_AGENT = "GenerativeArtLab-content-check/1.0 (https://github.com/abc-u/generative-art-lab)"

S = {"type": "string"}
def text(min_length=1, max_length=None):
    rule = {"type": "string", "minLength": min_length}
    if max_length: rule["maxLength"] = max_length
    return rule
def obj(required, properties):
    return {"type": "object", "additionalProperties": False, "required": required, "properties": properties}

# The shape lesson.js renders. Day 1 predates it and is written directly in lesson.html.
SCHEMA = obj(
    ["day", "status", "title", "subtitle", "topic", "phase", "minutes", "level", "algorithm", "applications", "prerequisites",
     "connection", "intuition", "numbers", "code", "demo", "experiments", "artist", "extension"],
    {
        "day": {"type": "integer", "minimum": 2},
        "status": {"type": "string", "enum": ["published"]},
        "title": text(3, 80),
        "subtitle": text(5, 140),
        "topic": text(2, 40),
        "phase": {"type": "integer", "minimum": 1},
        "minutes": {"type": "integer", "minimum": 15, "maximum": 20},
        "level": text(2, 20),
        "algorithm": text(120),
        "applications": text(40),
        "prerequisites": text(30),
        "connection": text(40),
        "ruleSummary": text(10, 160),
        "codeNote": text(10, 180),
        "intuition": obj(["title", "story", "visual", "diagram"], {"title": text(3), "story": text(100), "visual": text(20), "diagram": text(20)}),
        "numbers": obj(["setup", "steps", "note"], {
            "setup": text(50),
            "steps": {"type": "array", "minItems": 3, "maxItems": 6, "items": obj(["label", "calculation"], {"label": text(), "calculation": text()})},
            "note": text(40)}),
        "code": text(40),
        "demo": obj(["title", "caption", "html"], {"title": text(3), "caption": text(20), "html": text(500)}),
        "experiments": {"type": "array", "minItems": 4, "maxItems": 6, "items": obj(["title", "action", "observe"], {"title": text(), "action": text(30), "observe": text(30), "demoState": {"type": "array", "maxItems": 10, "items": obj(["selector", "value"], {"selector": text(2), "value": text()})}})},
        "artist": obj(["name", "work", "context", "relation", "references", "image"], {
            "name": text(), "work": text(), "context": text(80), "relation": text(60),
            "references": {"type": "array", "minItems": 1, "maxItems": 3, "items": obj(["source", "label", "url"], {"source": text(), "label": text(), "url": {"type": "string", "pattern": "^https://"}})},
            "image": {"anyOf": [{"type": "null"}, obj(["url", "alt", "sourceUrl", "license", "credit"], {
                "url": {"type": "string", "pattern": "^https://"}, "alt": text(20), "sourceUrl": {"type": "string", "pattern": "^https://"},
                "license": {"type": "string", "enum": ALLOWED_LICENSES}, "credit": text(3)})]}}),
        "extension": obj(["keywords", "next"], {"keywords": {"type": "array", "minItems": 3, "maxItems": 6, "items": text()}, "next": text(40)}),
    },
)

TYPES = {"object": dict, "array": list, "string": str, "integer": int, "null": type(None)}

def check_schema(value, rule, path, problems):
    if "anyOf" in rule:
        for option in rule["anyOf"]:
            trial = []
            check_schema(value, option, path, trial)
            if not trial: return
        problems.append(f"{path}: does not match any allowed shape")
        return
    expected = TYPES[rule["type"]]
    if not isinstance(value, expected) or (rule["type"] == "integer" and isinstance(value, bool)):
        problems.append(f"{path}: expected {rule['type']}")
        return
    if "enum" in rule and value not in rule["enum"]: problems.append(f"{path}: must be one of {rule['enum']}")
    if rule["type"] == "string":
        if len(value.strip()) < rule.get("minLength", 0): problems.append(f"{path}: shorter than {rule['minLength']} characters")
        if "maxLength" in rule and len(value) > rule["maxLength"]: problems.append(f"{path}: longer than {rule['maxLength']} characters")
        if "pattern" in rule and not re.search(rule["pattern"], value): problems.append(f"{path}: does not match {rule['pattern']}")
    if rule["type"] == "integer":
        if "minimum" in rule and value < rule["minimum"]: problems.append(f"{path}: below {rule['minimum']}")
        if "maximum" in rule and value > rule["maximum"]: problems.append(f"{path}: above {rule['maximum']}")
    if rule["type"] == "array":
        if len(value) < rule.get("minItems", 0): problems.append(f"{path}: needs at least {rule['minItems']} items")
        if "maxItems" in rule and len(value) > rule["maxItems"]: problems.append(f"{path}: allows at most {rule['maxItems']} items")
        for index, item in enumerate(value): check_schema(item, rule["items"], f"{path}[{index}]", problems)
    if rule["type"] == "object":
        for key in rule["required"]:
            if key not in value: problems.append(f"{path}.{key}: missing")
        for key, item in value.items():
            if key not in rule["properties"]: problems.append(f"{path}.{key}: unexpected field")
            else: check_schema(item, rule["properties"][key], f"{path}.{key}", problems)

class DemoParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.forbidden = []; self.scripts = 0; self.canvas = 0; self.controls = 0; self.viewport = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "canvas": self.canvas += 1
        if tag in {"input", "button", "select"}: self.controls += 1
        if tag == "script": self.scripts += 1
        if tag == "meta" and attrs.get("name") == "viewport": self.viewport = True
        if tag in {"iframe", "object", "embed", "form", "link", "base"}: self.forbidden.append(f"<{tag}>")
        if any(key.lower().startswith("on") for key in attrs): self.forbidden.append(f"inline event attribute on <{tag}>")
        if tag in {"script", "img", "audio", "video", "source"} and attrs.get("src"): self.forbidden.append(f"external asset on <{tag}>")

def node_check(source):
    result = subprocess.run(["node", "--check", "--input-type=commonjs"], input=source.encode(), capture_output=True)
    return result.stderr.decode(errors="replace")[:400] if result.returncode else None

def fetch(url, method="GET"):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read(3_000_000).decode(errors="replace") if method == "GET" else ""
        return response.status, response.headers.get("Content-Type", ""), body

def validate_lesson(path, curriculum, offline):
    problems = []
    try:
        lesson = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        return [f"{path.name}: invalid JSON ({error})"]
    check_schema(lesson, SCHEMA, "lesson", problems)
    if problems: return problems

    day = lesson["day"]
    if path.name != f"day-{day:02}.json": problems.append(f"file name should be day-{day:02}.json")
    entry = next((item for item in curriculum["lessons"] if item["day"] == day), None)
    if entry is None: problems.append(f"curriculum.json has no entry for Day {day}")
    else:
        if entry["status"] != "published": problems.append(f"curriculum.json Day {day} status must be published")
        if entry["title"] != lesson["title"]: problems.append("curriculum title differs from the lesson title")
        if entry["phase"] != lesson["phase"]: problems.append("curriculum phase differs from the lesson phase")
    if lesson["phase"] not in {phase["id"] for phase in curriculum["phases"]}: problems.append(f"phase {lesson['phase']} is not defined in curriculum.json")
    others = {item["title"].strip().casefold() for item in curriculum["lessons"] if item["day"] != day and item["status"] == "published"}
    if lesson["title"].strip().casefold() in others: problems.append("another published lesson already uses this title")

    code = lesson["code"]
    if re.search(r"<\s*script|javascript:", code, re.I): problems.append("code sample contains unsafe markup")
    error = node_check("function lesson(){\n" + code + "\n}\n")
    if error: problems.append("code sample has a syntax error: " + error)

    demo = lesson["demo"]["html"]
    parser = DemoParser(); parser.feed(demo)
    problems += [f"demo contains {item}" for item in parser.forbidden]
    if parser.canvas < 1: problems.append("demo needs a <canvas>")
    if parser.controls < 1: problems.append("demo needs at least one input, button or select")
    if parser.scripts < 1: problems.append("demo needs inline JavaScript")
    if not parser.viewport: problems.append('demo needs <meta name="viewport"> so it fits phones')
    for script in re.findall(r"<script\b[^>]*>(.*?)</script\s*>", demo, re.I | re.S):
        error = node_check(script)
        if error: problems.append("demo JavaScript has a syntax error: " + error)
    if re.search(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|importScripts)\s*\(|\bimport\s*\(", demo): problems.append("demo must not make network requests")
    stripped = re.sub(r"<!--.*?-->|http://www\.w3\.org/[\w/.-]*", "", demo, flags=re.S)  # SVG namespaces are not requests
    if re.search(r"https?://", stripped): problems.append("demo must not reference external URLs")

    artist = lesson["artist"]
    image = artist["image"]
    reference_urls = [reference["url"] for reference in artist["references"]]
    if image is not None:
        if image["sourceUrl"] not in reference_urls: problems.append("image.sourceUrl must also be listed in artist.references")
        if urllib.parse.urlparse(image["url"]).hostname != "upload.wikimedia.org": problems.append("artist images must be served from upload.wikimedia.org")
        if urllib.parse.urlparse(image["sourceUrl"]).hostname != "commons.wikimedia.org": problems.append("image.sourceUrl must be a commons.wikimedia.org file page")
    if offline: return problems

    pages = {}
    for url in reference_urls:
        try:
            status, _, body = fetch(url)
            if status >= 400: problems.append(f"reference returned HTTP {status}: {url}")
            pages[url] = body
        except (urllib.error.URLError, TimeoutError) as error:
            problems.append(f"reference could not be opened: {url} ({error})")
    if image is not None:
        license_name = image["license"].lower()
        aliases = {"public domain": ["public domain", "pd-"], "cc0 1.0": ["cc0", "creative commons zero"], "cc by 4.0": ["cc by 4.0", "cc-by-4.0"], "cc by-sa 4.0": ["cc by-sa 4.0", "cc-by-sa-4.0"]}[license_name]
        if not any(alias in pages.get(image["sourceUrl"], "").lower() for alias in aliases): problems.append("the Commons file page does not confirm the declared license")
        try:
            _, content_type, _ = fetch(image["url"], method="HEAD")
            if not content_type.lower().startswith("image/"): problems.append("image.url is not served as an image")
        except (urllib.error.URLError, TimeoutError) as error:
            problems.append(f"image could not be opened: {image['url']} ({error})")
    return problems

def validate_curriculum(curriculum):
    problems = []
    days = [item["day"] for item in curriculum["lessons"]]
    if days != list(range(1, len(days) + 1)): problems.append("curriculum days must run 1, 2, 3 … without gaps")
    published = [item["day"] for item in curriculum["lessons"] if item["status"] == "published"]
    if published != list(range(1, len(published) + 1)): problems.append("published days must be consecutive from Day 1")
    phase_ids = {phase["id"] for phase in curriculum["phases"]}
    for item in curriculum["lessons"]:
        if item["status"] not in {"published", "planned"}: problems.append(f"Day {item['day']}: unknown status {item['status']}")
        if item["phase"] not in phase_ids: problems.append(f"Day {item['day']}: phase {item['phase']} is not defined")
        if item["status"] == "published" and item["day"] > 1 and not (LESSONS / f"day-{item['day']:02}.json").exists():
            problems.append(f"Day {item['day']} is published but lessons/day-{item['day']:02}.json is missing")
    titles = [item["title"].strip().casefold() for item in curriculum["lessons"]]
    duplicates = sorted({title for title in titles if titles.count(title) > 1})
    if duplicates: problems.append("duplicate curriculum titles: " + ", ".join(duplicates))
    return problems

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lessons", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="validate every published lesson file")
    parser.add_argument("--offline", action="store_true", help="skip network checks")
    args = parser.parse_args()
    curriculum = json.loads(CURRICULUM.read_text())
    paths = args.lessons
    if args.all:
        paths = [LESSONS / f"day-{item['day']:02}.json" for item in curriculum["lessons"] if item["status"] == "published" and item["day"] > 1]
    report = {"curriculum.json": validate_curriculum(curriculum)}
    for path in paths:
        report[str(path)] = validate_lesson(path if path.is_absolute() else Path.cwd() / path, curriculum, args.offline)
    failed = False
    for name, problems in report.items():
        print(f"{'FAIL' if problems else 'ok  '} {name}")
        for problem in problems: print(f"     - {problem}")
        failed = failed or bool(problems)
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
