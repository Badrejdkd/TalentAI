"""
Outils de la crew TalentAI.

- charger_cv          : extraction du texte d'un CV (document loaders LangChain)
- anonymiser          : suppression des données personnelles AVANT l'IA
- VerifierCompetencesTool : outil CrewAI de vérification factuelle des compétences
"""
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Registre des CV anonymisés de l'exécution en cours (rempli par @before_kickoff)
CV_ANONYMISES: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Extraction (LangChain)
# ---------------------------------------------------------------------------
def charger_cv(chemin: str | Path) -> str:
    from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader

    chemin = str(chemin)
    ext = Path(chemin).suffix.lower()
    if ext == ".pdf":
        loader = PyPDFLoader(chemin)
    elif ext == ".docx":
        loader = Docx2txtLoader(chemin)
    elif ext in (".txt", ".md"):
        loader = TextLoader(chemin, autodetect_encoding=True)
    else:
        raise ValueError(f"Format non supporté : {ext}")
    return "\n".join(d.page_content for d in loader.load()).strip()


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
RE_TEL = re.compile(r"(?:\+212|00212|0)\s?[5-7](?:[\s.-]?\d{2}){4}|\+\d{1,3}[\s.-]?\d(?:[\s.-]?\d{2,3}){3,5}")
RE_LIEN = re.compile(r"(?:https?://|www\.)\S+|(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w-]+/?", re.I)
MOTIFS = [
    (re.compile(r"(?im)^.*\b(n[ée]e?\s+le|date\s+de\s+naissance|lieu\s+de\s+naissance)\b.*$"), "[naissance masquée]"),
    (re.compile(r"(?i)\b\d{2}\s*ans\b(?!\s*d)"), "[âge masqué]"),
    (re.compile(r"(?im)^.*\b(situation\s+familiale|mari[ée]e?|c[ée]libataire|divorc[ée]e?|veu[fv]e?)\b.*$"), "[situation familiale masquée]"),
    (re.compile(r"(?im)^.*\b(nationalit[ée]|sexe|genre|religion)\b.*$"), "[information personnelle masquée]"),
    (re.compile(r"(?im)^.*\b(adresse|domicile)\b.*$"), "[adresse masquée]"),
    (re.compile(r"(?i)\b(CIN|C\.I\.N\.?)\s*[:\-]?\s*[A-Z]{1,2}\d{3,7}\b"), "[CIN masquée]"),
]


def anonymiser(texte: str) -> str:
    """Masque coordonnées et données sensibles ; le nom (1re ligne) est remplacé par [CANDIDAT]."""
    texte = RE_EMAIL.sub("[email masqué]", texte)
    texte = RE_LIEN.sub("[lien masqué]", texte)
    texte = RE_TEL.sub("[téléphone masqué]", texte)
    lignes = texte.strip().splitlines()
    if lignes and len(lignes[0]) < 45 and not re.search(r"\d|@|\[", lignes[0]):
        for mot in lignes[0].split():
            if len(mot) > 1:
                texte = re.sub(rf"(?i)\b{re.escape(mot)}\b", "[CANDIDAT]", texte)
    for motif, rempl in MOTIFS:
        texte = motif.sub(rempl, texte)
    return re.sub(r"[ \t]{2,}", " ", texte).strip()


# ---------------------------------------------------------------------------
# Outil CrewAI
# ---------------------------------------------------------------------------
def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower())


class VerifierCompetencesInput(BaseModel):
    candidat_id: str = Field(description="Identifiant anonyme du candidat, ex. C01")
    competences_json: str = Field(description='Liste JSON des compétences de la grille, ex. ["Python", "SQL"]')


class VerifierCompetencesTool(BaseTool):
    name: str = "verifier_competences_cv"
    description: str = (
        "Vérifie mot à mot quelles compétences apparaissent réellement dans le CV anonymisé d'un candidat. "
        "Retourne les compétences trouvées, manquantes et le taux de couverture (%). "
        "À utiliser pour chaque candidat AVANT de le noter."
    )
    args_schema: Type[BaseModel] = VerifierCompetencesInput

    def _run(self, candidat_id: str, competences_json: str) -> str:
        cv = CV_ANONYMISES.get(candidat_id.strip().strip("[]"))
        if cv is None:
            return json.dumps({"erreur": f"Candidat inconnu : {candidat_id}. Identifiants : {list(CV_ANONYMISES)}"})
        try:
            comps = json.loads(competences_json)
        except json.JSONDecodeError:
            comps = [c.strip() for c in competences_json.split(",") if c.strip()]
        texte = _norm(cv)
        trouvees, manquantes = [], []
        for c in comps:
            variantes = [_norm(v).strip() for v in re.split(r"[/,()]", str(c)) if len(v.strip()) > 1]
            ok = any(re.search(r"(?<![a-z0-9])" + re.escape(v) + r"(?![a-z0-9])", texte) for v in variantes)
            (trouvees if ok else manquantes).append(c)
        taux = round(100 * len(trouvees) / len(comps), 1) if comps else 0.0
        return json.dumps({"candidat_id": candidat_id, "trouvees": trouvees, "manquantes": manquantes,
                           "taux_couverture": taux}, ensure_ascii=False)
