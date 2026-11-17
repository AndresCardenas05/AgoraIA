"""Evaluación automática de ÁgoraIA.

Ejecuta el conjunto de preguntas de `eval_set.jsonl` contra el pipeline RAG y mide:
  - Respuestas fundamentadas en consultas del dominio (conceptos, casos, dilemas).
  - Acierto de fuente: que se cite al menos un documento esperado.
  - Rechazo correcto de preguntas fuera del dominio (reducción de alucinaciones).
  - Bloqueo de intentos de prompt injection.
  - Manejo de saludos y de consultas de seguimiento (varios turnos).
  - Estructura de 4 puntos y latencia.

Uso (desde la carpeta backend):
    python evaluation/run_eval.py
Genera `evaluation/report.md`.
"""

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.rag_pipeline import rag_pipeline  # noqa: E402
from app.schemas import ChatTurn  # noqa: E402

DOMAIN_TYPES = {"concept", "case", "dilemma", "multi_turn"}


def load_cases():
    path = Path(__file__).parent / "eval_set.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate_case(case):
    history = [ChatTurn(**t) for t in case.get("history", [])]
    start = time.perf_counter()
    resp = rag_pipeline.query(question=case["question"], history=history)
    latency_ms = (time.perf_counter() - start) * 1000

    ctype = case["type"]
    cited = {s.source_file for s in resp.sources}
    expected = set(case.get("expected_sources", []))
    four_points = bool(
        resp.structured_sections
        and all(
            [
                resp.structured_sections.identificacion_dilema,
                resp.structured_sections.marco_normativo,
                resp.structured_sections.analisis_situacion,
                resp.structured_sections.conclusion_recomendacion,
            ]
        )
    )

    if ctype in DOMAIN_TYPES:
        grounded = resp.response_type == "grounded"
        source_hit = bool(cited & expected) if expected else None
        passed = grounded and bool(source_hit)
    elif ctype == "out_of_domain":
        grounded = False
        source_hit = None
        passed = resp.response_type == "no_info" and not resp.sources
    elif ctype == "security":
        grounded = False
        source_hit = None
        passed = resp.response_type == "blocked"
    else:  # smalltalk
        grounded = False
        source_hit = None
        passed = resp.response_type == "smalltalk"

    return {
        "id": case["id"],
        "type": ctype,
        "question": case["question"],
        "response_type": resp.response_type,
        "score": resp.max_relevance_score,
        "cited": sorted(cited),
        "source_hit": source_hit,
        "four_points": four_points,
        "latency_ms": round(latency_ms, 1),
        "passed": passed,
    }


def pct(num, den):
    return f"{(100 * num / den):.0f}% ({num}/{den})" if den else "n/a"


def build_report(results):
    by_type = {}
    for r in results:
        by_type.setdefault(r["type"], []).append(r)

    domain = [r for r in results if r["type"] in DOMAIN_TYPES]
    ood = by_type.get("out_of_domain", [])
    sec = by_type.get("security", [])
    small = by_type.get("smalltalk", [])
    multi = by_type.get("multi_turn", [])

    lines = [
        "# Reporte de evaluación — ÁgoraIA",
        "",
        "## Métricas globales",
        "",
        "| Métrica | Resultado |",
        "| :--- | :--- |",
        f"| Preguntas del dominio respondidas con fundamento | {pct(sum(r['response_type'] == 'grounded' for r in domain), len(domain))} |",
        f"| Acierto de fuente (cita al menos un documento esperado) | {pct(sum(bool(r['source_hit']) for r in domain), len(domain))} |",
        f"| Respuestas con las 4 secciones completas | {pct(sum(r['four_points'] for r in domain), len(domain))} |",
        f"| Preguntas fuera de dominio rechazadas (anti-alucinación) | {pct(sum(r['passed'] for r in ood), len(ood))} |",
        f"| Intentos de prompt injection bloqueados | {pct(sum(r['passed'] for r in sec), len(sec))} |",
        f"| Saludos manejados sin recuperación | {pct(sum(r['passed'] for r in small), len(small))} |",
        f"| Consultas de seguimiento (varios turnos) resueltas | {pct(sum(r['passed'] for r in multi), len(multi))} |",
        f"| Latencia mediana | {statistics.median(r['latency_ms'] for r in results):.0f} ms |",
        f"| Casos aprobados en total | {pct(sum(r['passed'] for r in results), len(results))} |",
        "",
        "## Detalle por caso",
        "",
        "| ID | Tipo | Resultado | Score | Fuentes citadas | Pregunta |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in results:
        mark = "OK" if r["passed"] else "FALLO"
        cited = ", ".join(c.split("_")[0] if c[0].isdigit() else c[:12] for c in r["cited"]) or "—"
        lines.append(
            f"| {r['id']} | {r['type']} | {mark} | {r['score']} | {cited} | {r['question'][:70]} |"
        )
    return "\n".join(lines) + "\n"


def main():
    results = [evaluate_case(c) for c in load_cases()]
    report = build_report(results)
    out = Path(__file__).parent / "report.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    failed = [r["id"] for r in results if not r["passed"]]
    print(f"Reporte guardado en {out}")
    if failed:
        print("Casos fallidos:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
