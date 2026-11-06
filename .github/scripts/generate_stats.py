#!/usr/bin/env python3
"""Gera assets/stats.svg e assets/languages.svg com a API do GitHub.

Roda dentro do GitHub Actions (usa o GITHUB_TOKEN automático), sem depender
de serviços de terceiros que ficam sem cota. Só biblioteca padrão do Python.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "tirolasca"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "assets")
API = "https://api.github.com"

FONT = "'Segoe UI',Inter,Helvetica,Arial,sans-serif"
LANG_COLORS = {
    "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#8a63d2",
    "Python": "#3572a5", "Java": "#b07219", "Astro": "#ff5a03", "PHP": "#4f5d95",
    "C#": "#178600", "Shell": "#89e051", "SCSS": "#c6538c", "Vue": "#41b883",
    "Dockerfile": "#384d54", "C": "#555555", "C++": "#f34b7d", "Kotlin": "#a97bff",
    "Go": "#00add8", "Rust": "#dea584", "Dart": "#00b4ab", "Jupyter Notebook": "#da5b0b",
}
FALLBACK = ["#00f0d1", "#00aaff", "#ffd166", "#00ff80", "#c084fc", "#fb7185"]


def get(path, params=None):
    url = API + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-stats-generator",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 2:
                time.sleep(20 * (attempt + 1))
                continue
            raise


def collect():
    user = get(f"/users/{USER}")
    repos, page = [], 1
    while True:
        chunk = get(f"/users/{USER}/repos", {"per_page": 100, "page": page, "type": "owner"})
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = {}
    for r in own:
        for name, size in get(f"/repos/{USER}/{r['name']}/languages").items():
            langs[name] = langs.get(name, 0) + size
    time.sleep(2)
    commits = get("/search/commits", {"q": f"author:{USER}", "per_page": 1})["total_count"]
    time.sleep(2)
    prs = get("/search/issues", {"q": f"author:{USER} type:pr", "per_page": 1})["total_count"]
    time.sleep(2)
    issues = get("/search/issues", {"q": f"author:{USER} type:issue", "per_page": 1})["total_count"]
    return {
        "stars": sum(r["stargazers_count"] for r in own),
        "commits": commits, "prs": prs, "issues": issues,
        "repos": user["public_repos"], "followers": user["followers"],
        "langs": langs,
    }


STYLE = f"""<style>
.t{{font:700 18px {FONT};fill:#00f0d1}}
.n{{font:800 22px {FONT}}}
.l{{font:500 12px {FONT};fill:#9fb8bd}}
.ln{{font:600 13px {FONT};fill:#e6f4f1}}
.p{{font:500 12px {FONT};fill:#9fb8bd}}
.i{{opacity:0;animation:in .6s ease forwards}}
@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.i{{animation:none;opacity:1}}animate{{display:none}}}}
</style>"""


def card(title, body, desc):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="210" viewBox="0 0 420 210" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title><desc>{escape(desc)}</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#04171b"/><stop offset="1" stop-color="#020b0e"/></linearGradient>
<linearGradient id="ac" x1="0" x2="1"><stop offset="0" stop-color="#00f0d1"/><stop offset="1" stop-color="#00aaff"/></linearGradient></defs>
{STYLE}
<rect x=".75" y=".75" width="418.5" height="208.5" rx="14" fill="url(#bg)" stroke="#00f0d1" stroke-opacity=".4" stroke-width="1.5"/>
<rect x="24" y="52" width="40" height="2" rx="1" fill="url(#ac)"/>
<text x="24" y="38" class="t">{escape(title)}</text>
{body}
</svg>"""


def fmt(n):
    return f"{n:,}".replace(",", ".")


def stats_svg(d):
    cells = [("Estrelas recebidas", d["stars"], "#ffd166"), ("Commits públicos", d["commits"], "#00f0d1"),
             ("Pull requests", d["prs"], "#00aaff"), ("Issues abertas por mim", d["issues"], "#00ff80"),
             ("Repositórios públicos", d["repos"], "#00f0d1"), ("Seguidores", d["followers"], "#00aaff")]
    out = []
    for i, (label, val, color) in enumerate(cells):
        x = 24 + (i % 2) * 190
        y = 90 + (i // 2) * 40
        out.append(f'<g class="i" style="animation-delay:{i*0.08:.2f}s"><text x="{x}" y="{y}" class="n" fill="{color}">{fmt(val)}</text>'
                   f'<text x="{x}" y="{y+15}" class="l">{escape(label)}</text></g>')
    return card("Estatísticas do GitHub", "\n".join(out), "Estrelas, commits, pull requests, issues, repositórios e seguidores de " + USER)


def langs_svg(d):
    total = sum(d["langs"].values()) or 1
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:6]
    out = []
    for i, (name, size) in enumerate(top):
        pct = size / total * 100
        color = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
        y = 78 + i * 22
        w = max(3, 190 * pct / 100 * (100 / max(top[0][1] / total * 100, 1)) * 0.92)
        out.append(f'<g class="i" style="animation-delay:{i*0.08:.2f}s"><text x="24" y="{y}" class="ln">{escape(name)}</text>'
                   f'<rect x="132" y="{y-9}" width="200" height="8" rx="4" fill="#ffffff" fill-opacity=".08"/>'
                   f'<rect x="132" y="{y-9}" width="0" height="8" rx="4" fill="{color}"><animate attributeName="width" from="0" to="{min(w,200):.1f}" dur="1s" begin="{i*0.1:.1f}s" fill="freeze"/></rect>'
                   f'<text x="396" y="{y}" class="p" text-anchor="end">{pct:.1f}%</text></g>')
    return card("Linguagens mais utilizadas", "\n".join(out), "Linguagens mais usadas nos repositórios de " + USER)


def main():
    try:
        data = collect()
    except Exception as e:  # não sobrescreve os SVGs existentes se a API falhar
        print("Falha ao coletar dados:", e, file=sys.stderr)
        sys.exit(1)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(data))
    with open(os.path.join(OUT, "languages.svg"), "w", encoding="utf-8") as f:
        f.write(langs_svg(data))
    print("OK:", {k: v for k, v in data.items() if k != "langs"}, list(data["langs"])[:6])


if __name__ == "__main__":
    main()
