"""Собирает frontend/public/teacher-guide.html из docs/TEACHER_GUIDE.md.

Страница открывается по ссылке «Инструкция преподавателю» в кабинете. Запускать после правок инструкции:
    python scripts/build_teacher_guide.py
Конвертер минимальный (заголовки, списки, таблицы, код, жирный, ссылки): внешних библиотек нет.
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "TEACHER_GUIDE.md"
DST = ROOT / "frontend" / "public" / "teacher-guide.html"


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def convert(md):
    out, lines, i = [], md.split("\n"), 0
    list_tag = None

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</li></{list_tag}>")
            list_tag = None

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            close_list()
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(html.escape(lines[i], quote=False))
                i += 1
            out.append("<pre><code>" + "\n".join(block) + "</code></pre>")
        elif line.startswith("|"):
            close_list()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            i -= 1
            out.append("<table>")
            for n, row in enumerate(rows):
                if n == 1 and all(set(c) <= set("-: ") for c in row):
                    continue
                tag = "th" if n == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in row) + "</tr>")
            out.append("</table>")
        elif re.match(r"^#{1,4} ", line):
            close_list()
            level = len(line.split(" ")[0])
            out.append(f"<h{level}>{inline(line[level + 1:])}</h{level}>")
        elif re.match(r"^\s*(\d+\.|[-*]) ", line):
            ordered = bool(re.match(r"^\s*\d+\.", line))
            tag = "ol" if ordered else "ul"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            else:
                out.append("</li>")
            out.append("<li>" + inline(re.sub(r"^\s*(\d+\.|[-*]) ", "", line)))
        elif line.startswith("   ") and list_tag:
            out.append(" " + inline(line.strip()))
        elif line.strip() == "":
            close_list()
        else:
            close_list()
            out.append(f"<p>{inline(line)}</p>")
        i += 1
    close_list()
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Инструкция преподавателю</title>
<style>
:root { --bg:#fbf7ee; --text:#2a2118; --muted:#6b5d4a; --line:#d9ccb2; --code:#efe6d2; --link:#8a4b12; }
@media (prefers-color-scheme: dark) { :root { --bg:#14110d; --text:#ece3d0; --muted:#b5a88f; --line:#3a3226; --code:#221d15; --link:#e0a35a; } }
body { background:var(--bg); color:var(--text); font:16px/1.6 system-ui, sans-serif; margin:0; padding:24px 16px 64px; }
main { max-width:760px; margin:0 auto; }
h1,h2,h3 { line-height:1.25; } h2 { margin-top:2em; border-bottom:1px solid var(--line); padding-bottom:.2em; }
a { color:var(--link); } code { background:var(--code); padding:.1em .35em; border-radius:4px; font-size:.92em; }
pre { background:var(--code); padding:12px; border-radius:8px; overflow-x:auto; } pre code { padding:0; }
table { border-collapse:collapse; width:100%; display:block; overflow-x:auto; } th,td { border:1px solid var(--line); padding:6px 10px; text-align:left; vertical-align:top; }
</style>
</head>
<body><main>
@@BODY@@
</main></body>
</html>
"""

if __name__ == "__main__":
    DST.write_text(PAGE.replace("@@BODY@@", convert(SRC.read_text(encoding="utf-8"))), encoding="utf-8")
    print("written", DST)
