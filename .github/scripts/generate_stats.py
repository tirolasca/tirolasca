#!/usr/bin/env python3
"""Gera os cartões SVG do perfil (variantes escura e clara) com a API do GitHub.

  stats, languages  -> estatísticas e linguagens dos repositórios
  streak            -> sequência de contribuições (GraphQL, últimos 12 meses)
  numbers           -> projetos/tecnologias/categorias do portfólio (lidos do repo Portfolio)

Roda dentro do GitHub Actions (usa o GITHUB_TOKEN automático), sem depender
de serviços de terceiros que ficam sem cota. Só biblioteca padrão do Python.
O que falhar no streak/numbers não derruba o resto (o arquivo anterior é mantido).
"""
import json
import os
import re
import sys
import time
import datetime
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


THEMES = {
    "dark": {
        "suffix": "", "bg0": "#04171b", "bg1": "#020b0e", "stroke": "#00f0d1", "stroke_op": ".4",
        "ac0": "#00f0d1", "ac1": "#00aaff", "title": "#00f0d1", "label": "#9fb8bd", "text": "#e6f4f1",
        "track": "#ffffff", "track_op": ".08",
        "gold": "#ffd166", "cyan": "#00f0d1", "blue": "#00aaff", "green": "#00ff80",
    },
    "light": {
        "suffix": "-light", "bg0": "#ffffff", "bg1": "#eaf6f6", "stroke": "#0aa89a", "stroke_op": ".55",
        "ac0": "#0aa89a", "ac1": "#0a84d6", "title": "#0a7d72", "label": "#4b6a72", "text": "#14343b",
        "track": "#0a3d44", "track_op": ".10",
        "gold": "#b7791f", "cyan": "#0a8f84", "blue": "#0b6fb8", "green": "#178a4a",
    },
}


def style(t):
    return f"""<style>
.t{{font:700 18px {FONT};fill:{t['title']}}}
.n{{font:800 22px {FONT}}}
.l{{font:500 12px {FONT};fill:{t['label']}}}
.ln{{font:600 13px {FONT};fill:{t['text']}}}
.p{{font:500 12px {FONT};fill:{t['label']}}}
.i{{opacity:0;animation:in .6s ease forwards}}
@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.i{{animation:none;opacity:1}}animate{{display:none}}}}
</style>"""


def card(title, body, desc, t, w=420, h=210):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title><desc>{escape(desc)}</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg0']}"/><stop offset="1" stop-color="{t['bg1']}"/></linearGradient>
<linearGradient id="ac" x1="0" x2="1"><stop offset="0" stop-color="{t['ac0']}"/><stop offset="1" stop-color="{t['ac1']}"/></linearGradient></defs>
{style(t)}
<rect x=".75" y=".75" width="{w-1.5}" height="{h-1.5}" rx="14" fill="url(#bg)" stroke="{t['stroke']}" stroke-opacity="{t['stroke_op']}" stroke-width="1.5"/>
<rect x="24" y="52" width="40" height="2" rx="1" fill="url(#ac)"/>
<text x="24" y="38" class="t">{escape(title)}</text>
{body}
</svg>"""


def fmt(n):
    return f"{n:,}".replace(",", ".")


def stats_svg(d, t):
    cells = [("Estrelas recebidas", d["stars"], t["gold"]), ("Commits públicos", d["commits"], t["cyan"]),
             ("Pull requests", d["prs"], t["blue"]), ("Issues abertas por mim", d["issues"], t["green"]),
             ("Repositórios públicos", d["repos"], t["cyan"]), ("Seguidores", d["followers"], t["blue"])]
    out = []
    for i, (label, val, color) in enumerate(cells):
        x = 24 + (i % 2) * 190
        y = 90 + (i // 2) * 40
        out.append(f'<g class="i" style="animation-delay:{i*0.08:.2f}s"><text x="{x}" y="{y}" class="n" fill="{color}">{fmt(val)}</text>'
                   f'<text x="{x}" y="{y+15}" class="l">{escape(label)}</text></g>')
    return card("Estatísticas do GitHub", "\n".join(out), "Estrelas, commits, pull requests, issues, repositórios e seguidores de " + USER, t)


def langs_svg(d, t):
    total = sum(d["langs"].values()) or 1
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:6]
    out = []
    for i, (name, size) in enumerate(top):
        pct = size / total * 100
        color = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
        y = 78 + i * 22
        w = max(3, 190 * pct / 100 * (100 / max(top[0][1] / total * 100, 1)) * 0.92)
        out.append(f'<g class="i" style="animation-delay:{i*0.08:.2f}s"><text x="24" y="{y}" class="ln">{escape(name)}</text>'
                   f'<rect x="132" y="{y-9}" width="200" height="8" rx="4" fill="{t["track"]}" fill-opacity="{t["track_op"]}"/>'
                   f'<rect x="132" y="{y-9}" width="0" height="8" rx="4" fill="{color}"><animate attributeName="width" from="0" to="{min(w,200):.1f}" dur="1s" begin="{i*0.1:.1f}s" fill="freeze"/></rect>'
                   f'<text x="396" y="{y}" class="p" text-anchor="end">{pct:.1f}%</text></g>')
    return card("Linguagens mais utilizadas", "\n".join(out), "Linguagens mais usadas nos repositórios de " + USER, t)


def graphql(query, variables):
    req = urllib.request.Request(API + "/graphql", data=json.dumps({"query": query, "variables": variables}).encode(), headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-stats-generator",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if out.get("errors"):
        raise RuntimeError(out["errors"][0].get("message", "erro GraphQL"))
    return out["data"]


def collect_streak():
    """Total, sequência atual e maior sequência nos últimos 12 meses (limite do calendário do GitHub)."""
    q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
      totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    cal = graphql(q, {"login": USER})["user"]["contributionsCollection"]["contributionCalendar"]
    days = sorted((d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"])
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    days = [d for d in days if d[0] <= today]
    longest = run = 0
    for _, n in days:
        run = run + 1 if n > 0 else 0
        longest = max(longest, run)
    series = days[:-1] if days and days[-1][1] == 0 else days  # hoje sem commit ainda não zera a sequência
    current = 0
    for _, n in reversed(series):
        if n == 0:
            break
        current += 1
    return {"total": cal["totalContributions"], "current": current, "longest": longest}


def streak_svg(d, t):
    cols = [(f'{fmt(d["total"])}', "Contribuições em 12 meses", t["cyan"]),
            (f'{d["current"]}', "Sequência atual (dias)", t["gold"]),
            (f'{d["longest"]}', "Maior sequência em 12 meses", t["blue"])]
    out = []
    for i, (val, label, color) in enumerate(cols):
        x = 24 + 140 + i * 286  # centro de cada coluna (largura 860)
        out.append(f'<g class="i" style="animation-delay:{i*0.1:.1f}s"><text x="{x}" y="96" class="n" fill="{color}" text-anchor="middle" style="font-size:30px">{val}</text>'
                   f'<text x="{x}" y="118" class="l" text-anchor="middle">{escape(label)}</text></g>')
    return card("Sequência de contribuições", "\n".join(out), f"Contribuições, sequência atual e maior sequência de {USER} nos últimos 12 meses", t, 860, 140)


PORTFOLIO_RAW = "https://raw.githubusercontent.com/" + USER + "/Portfolio/main/src/data/"


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats-generator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def collect_portfolio():
    """Conta projetos, tecnologias e categorias lendo os dados do portfólio (fonte única)."""
    skills = fetch_text(PORTFOLIO_RAW + "skills.ts")
    projects = fetch_text(PORTFOLIO_RAW + "projects.ts")
    counts = {
        "projects": len(re.findall(r'^ {4}title: "', projects, re.M)),
        "techs": len(re.findall(r'\balt: "', skills)),
        "categories": len(re.findall(r'^\s+title: "', skills, re.M)),
    }
    if not all(counts.values()):
        raise RuntimeError(f"contagem vazia: {counts}")
    return counts


def numbers_svg(d, t):
    cols = [(d["projects"], "Projetos no portfólio", t["cyan"]), (d["techs"], "Tecnologias na stack", t["blue"]),
            (d["categories"], "Categorias de skills", t["gold"])]
    out = []
    for i, (val, label, color) in enumerate(cols):
        x = 24 + 140 + i * 286
        out.append(f'<g class="i" style="animation-delay:{i*0.1:.1f}s"><text x="{x}" y="96" class="n" fill="{color}" text-anchor="middle" style="font-size:30px">{val}</text>'
                   f'<text x="{x}" y="118" class="l" text-anchor="middle">{escape(label)}</text></g>')
    return card("Portfólio em números", "\n".join(out), "Quantidade de projetos, tecnologias e categorias de skills do portfólio de " + USER, t, 860, 140)


def write_all(name, render, data):
    for t in THEMES.values():
        with open(os.path.join(OUT, f"{name}{t['suffix']}.svg"), "w", encoding="utf-8") as f:
            f.write(render(data, t))


def main():
    try:
        data = collect()
    except Exception as e:  # não sobrescreve os SVGs existentes se a API falhar
        print("Falha ao coletar dados:", e, file=sys.stderr)
        sys.exit(1)
    os.makedirs(OUT, exist_ok=True)
    write_all("stats", stats_svg, data)
    write_all("languages", langs_svg, data)
    print("OK:", {k: v for k, v in data.items() if k != "langs"}, list(data["langs"])[:6])
    # extras: se falharem, mantêm o arquivo anterior e não derrubam o restante
    for name, collector, render in (("streak", collect_streak, streak_svg), ("numbers", collect_portfolio, numbers_svg)):
        try:
            extra = collector()
            write_all(name, render, extra)
            print(f"OK {name}:", extra)
        except Exception as e:
            print(f"Aviso: {name} não atualizado ({e})", file=sys.stderr)


if __name__ == "__main__":
    main()
