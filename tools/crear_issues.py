#!/usr/bin/env python3
"""Crea en GitHub las historias de prueba (docs/testing/historias.yml) con tu plantilla de historia de usuario.

    gh auth login                                  # una vez
    python tools/crear_issues.py                   # simulacro: muestra qué crearía
    python tools/crear_issues.py --crear           # crea los issues, los mete al Project y los cuelga de la épica/padre
    python tools/crear_issues.py --crear --proyecto "Trapitos"     # nombre del Project de la organización

Antes: pon los usuarios de GitHub en docs/testing/meta.yml -> personas (A, B, C). No duplica issues ya creados.
Sprint y puntos van como etiquetas (sprint:5, puntos:3); asígnalos en el Project con selección múltiple si usas campos.
Los bugs no se crean aquí: se reportan con la plantilla de issue «Defecto» (label bug).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_documentos import TESTING, cargar_catalogo  # noqa: E402


def gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check).stdout.strip()


def cuerpo(h, tcs, niveles):
    lineas = "\n".join(f"* `{c['id']}` — {c['name']} ({', '.join(c['reqs'])})" for c in tcs)
    reqs = sorted({r for c in tcs for r in c["reqs"]})
    nivel = ", ".join(sorted({niveles[c["level"]] for c in tcs}))
    auto = sum(1 for c in tcs if c.get("tests"))
    return (f"**Como** ingeniero de calidad de Mis Trapitos  \n"
            f"**Necesito** {h['titulo'][0].lower() + h['titulo'][1:]} ({len(tcs)} TC, nivel: {nivel})  \n"
            f"**Para que** cada PR confirme el comportamiento y los resultados alimenten el Test Report y Grafana  \n\n"
            f"### Detalles y Supuestos\n{lineas}\n\n"
            f"* Requisitos cubiertos: {', '.join(reqs)}.\n"
            f"* {auto} TC automatizados con pytest, {len(tcs) - auto} manuales.\n"
            f"* Cada TC se declara en su prueba con `@tc` y su docstring (ver `tests/tc.py`); los manuales en `docs/testing/manuales.yml`.\n"
            f"* Usar BD temporal (`load_examples=False`). Ver `docs/testing/README.md`.\n"
            f"* Padre: #{h['padre']} · Épica: #{h['epica']} · Estimación: {h['puntos']} pts · Sprint {h['sprint']}\n\n"
            f"### Criterios de Aceptación\n```gherkin\n"
            f"Dada una rama con la prueba (@tc y docstring) de cada TC listado\n"
            f"Cuando se abre el PR con «Closes #N»\n"
            f"Entonces tests.yml queda en verde y los TC aparecen con su estado en el Test Report\n```\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crear", action="store_true")
    ap.add_argument("--repo", help="owner/repo (por defecto el del clon actual)")
    ap.add_argument("--proyecto", help="título del Project para agregar los issues")
    a = ap.parse_args()
    cat = cargar_catalogo()
    hist = yaml.safe_load((TESTING / "historias.yml").read_text(encoding="utf-8"))
    meta, repo = cat["meta"], (["--repo", a.repo] if a.repo else [])
    personas = meta.get("personas") or {}
    nwo = a.repo or (gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner") if a.crear else "<repo>")
    existentes = {}
    if a.crear:
        for i in json.loads(gh("issue", "list", *repo, "--state", "all", "--limit", "500", "--json", "title,number")):
            existentes[i["title"]] = i["number"]
        for n, col in {"tipo:test-case": "0E8A16", "sprint:5": "FBCA04", "sprint:6": "FBCA04"}.items():
            gh("label", "create", n, "--color", col, "--force", *repo, check=False)
    ids_cubiertos = set()
    for h in hist["historias"]:
        h["epica"] = hist["epica"]
        tcs = [c for c in cat["cases"] if any(c["id"].startswith(p) for p in h["tcs"])]
        ids_cubiertos |= {c["id"] for c in tcs}
        titulo = f"[Test] {h['titulo']}"
        user = personas.get(h["persona"], "")
        print(f"{'CREA' if a.crear else 'simulacro'}: {titulo} · {len(tcs)} TC · {h['puntos']} pts · sprint {h['sprint']} · {user or '(sin asignar)'}")
        if titulo in existentes:
            print("   ya existe #%s" % existentes[titulo])
            continue
        if not a.crear:
            continue
        cmd = ["issue", "create", *repo, "--title", titulo, "--body", cuerpo(h, tcs, meta["levels"]),
               "--label", f"tipo:test-case,sprint:{h['sprint']},puntos:{h['puntos']}"]
        gh("label", "create", f"puntos:{h['puntos']}", "--color", "C5DEF5", "--force", *repo, check=False)
        if user:
            cmd += ["--assignee", user]
        if a.proyecto:
            cmd += ["--project", a.proyecto]
        url = gh(*cmd)
        num = url.rsplit("/", 1)[-1]
        print("   ", url)
        for padre in (h["padre"],):   # sub-issue del padre (y éste ya cuelga de la épica)
            try:
                sid = gh("api", f"repos/{nwo}/issues/{num}", "--jq", ".id")
                gh("api", "-X", "POST", f"repos/{nwo}/issues/{padre}/sub_issues", "-F", f"sub_issue_id={sid}")
            except subprocess.CalledProcessError as e:
                print(f"    (no pude colgarlo de #{padre}: {e.stderr.strip()[:80]}; hazlo a mano)")
    sueltos = [c["id"] for c in cat["cases"] if c["id"] not in ids_cubiertos]
    if sueltos:
        print("AVISO: TC sin historia:", ", ".join(sueltos))
    if not a.crear:
        print("\n(simulacro; usa --crear para crear de verdad)")


if __name__ == "__main__":
    main()
