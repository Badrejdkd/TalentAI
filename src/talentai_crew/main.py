#!/usr/bin/env python
"""
Points d'entrée CrewAI :
    crewai run                      -> exemple fourni (exemples/)
    uv run talentai_crew <dossier>  -> dossier contenant offre.txt, cvs/ et (option) creneaux.txt
    crewai train -n 3 -f train.pkl  /  crewai test -n 2  /  crewai replay -t <task_id>
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from talentai_crew.crew import TalentAICrew
from talentai_crew.tools import charger_cv

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_EXEMPLE = RACINE / "exemples"
SORTIE = RACINE / "sortie"


def construire_entrees(dossier: Path = DOSSIER_EXEMPLE) -> dict:
    """offre.txt (1re ligne = titre, ligne 'EXPERIENCE_MIN: n' facultative), cvs/*.pdf|docx|txt, creneaux.txt."""
    lignes = (dossier / "offre.txt").read_text(encoding="utf-8").strip().splitlines()
    titre, corps, exp = lignes[0].strip(), [], 0
    for l in lignes[1:]:
        if l.upper().startswith("EXPERIENCE_MIN:"):
            exp = int(l.split(":", 1)[1].strip() or 0)
        else:
            corps.append(l)
    fichiers = sorted(p for p in (dossier / "cvs").iterdir() if p.suffix.lower() in (".pdf", ".docx", ".txt"))
    cvs = [{"id": f"C{i:02d}", "texte": charger_cv(p)} for i, p in enumerate(fichiers, start=1)]
    correspondance = {f"C{i:02d}": p.name for i, p in enumerate(fichiers, start=1)}
    creneaux = dossier / "creneaux.txt"
    return {
        "offre_titre": titre,
        "offre_description": "\n".join(corps).strip(),
        "experience_min": exp,
        "cvs": cvs,
        "seuil_preselection": 70,
        "creneaux": creneaux.read_text(encoding="utf-8") if creneaux.exists() else "",
        "type_entretien": "visioconférence",
        "lieu": "https://meet.google.com/xxx-xxxx-xxx",
        "_correspondance": correspondance,
    }


def rapport_markdown(titre: str, res: dict, correspondance: dict) -> str:
    a, ev, qn, pl = res["analyse"], res["evaluations"], res["questionnaires"], res["planning"]
    md = [f"# Rapport de présélection — {titre}", f"_Généré le {datetime.now():%d/%m/%Y %H:%M} · "
          "**Recommandations IA : la décision finale appartient au recruteur.**_", "",
          "## 1. Grille de l'offre (Agent 1)", a["resume_poste"], "",
          "| Compétence | Niveau | Poids |", "|---|---|---|"]
    md += [f"| {c['nom']} | {c['niveau']} | {c['poids']} |" for c in a["competences"]]
    md += ["", "**Pondération :** " + " · ".join(f"{k} {v} %" for k, v in a["grille_ponderation"].items()),
           f"**Alertes de biais :** {', '.join(a['alertes_biais']) or 'aucune'}", "",
           "## 2. Classement des CV anonymisés (Agent 2)", "",
           "| Rang | Candidat | Fichier | Score | Recommandation |", "|---|---|---|---|---|"]
    for i, e in enumerate(sorted(ev["evaluations"], key=lambda e: -e["score_global"]), start=1):
        md.append(f"| {i} | {e['candidat_id']} | {correspondance.get(e['candidat_id'], '')} | "
                  f"{e['score_global']:.0f} | {e['recommandation']} |")
    for e in ev["evaluations"]:
        md += ["", f"### {e['candidat_id']} — {e['score_global']:.0f}/100", e["justification"],
               f"- Points forts : {'; '.join(e['points_forts'])}",
               f"- Vigilance : {'; '.join(e['points_vigilance']) or '—'}"]
    md += ["", "## 3. Questionnaires de pré-qualification (Agent 3)"]
    for q in qn["questionnaires"]:
        md += ["", f"### {q['candidat_id']}", f"> {q['message_accueil']}"] + \
              [f"{i}. {x['question']}" for i, x in enumerate(q["questions"], start=1)]
    md += ["", "## 4. Planning proposé (Agent 4) — à valider"]
    for p in pl["propositions"]:
        md += ["", f"### {p['candidat_id']} · {p['creneau']} · {p['type_entretien']} — _{p['statut']}_",
               f"**Objet :** {p['objet_email']}", "", "```", p["corps_email"], "```"]
    if pl["remarques"]:
        md += ["", f"**Remarques :** {pl['remarques']}"]
    md += ["", "---", "- [ ] Présélection validée par : ____________  Date : ________"]
    return "\n".join(md)


def executer(inputs: dict):
    correspondance = inputs.pop("_correspondance", {})
    resultat = TalentAICrew().crew().kickoff(inputs=inputs)
    sorties = [t.pydantic.model_dump() if t.pydantic else {"brut": t.raw} for t in resultat.tasks_output]
    res = dict(zip(["analyse", "evaluations", "questionnaires", "planning"], sorties))
    SORTIE.mkdir(exist_ok=True)
    (SORTIE / "resultats_preselection.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        (SORTIE / "rapport_preselection.md").write_text(rapport_markdown(inputs["offre_titre"], res, correspondance), encoding="utf-8")
    except (KeyError, TypeError):
        pass
    print(f"\n✅ Résultats : {SORTIE / 'rapport_preselection.md'}  et  resultats_preselection.json")
    print(f"   Tokens utilisés : {resultat.token_usage.total_tokens}")
    return res


def run():
    dossier = Path(sys.argv[1]) if len(sys.argv) > 1 else DOSSIER_EXEMPLE
    try:
        executer(construire_entrees(dossier))
    except Exception as e:
        raise Exception(f"Erreur pendant l'exécution de la crew : {e}")


def train():
    inputs = construire_entrees()
    inputs.pop("_correspondance")
    try:
        TalentAICrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)
    except Exception as e:
        raise Exception(f"Erreur pendant l'entraînement : {e}")


def replay():
    try:
        TalentAICrew().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"Erreur pendant le replay : {e}")


def test():
    inputs = construire_entrees()
    inputs.pop("_correspondance")
    try:
        TalentAICrew().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)
    except Exception as e:
        raise Exception(f"Erreur pendant le test : {e}")


def run_with_trigger():
    """Déclenchement par webhook / trigger CrewAI AMP : payload JSON en argument."""
    if len(sys.argv) < 2:
        raise Exception("Aucun payload fourni.")
    payload = json.loads(sys.argv[1])
    inputs = {"crewai_trigger_payload": payload, **{k: v for k, v in payload.items() if not k.startswith("_")}}
    return TalentAICrew().crew().kickoff(inputs=inputs)


if __name__ == "__main__":
    run()
