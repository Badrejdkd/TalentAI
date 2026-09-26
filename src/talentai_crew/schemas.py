"""
Sorties structurées des tâches (compatibles « Structured Outputs » strict d'OpenAI :
aucun dict libre, aucun champ facultatif).
"""
from typing import List

from pydantic import BaseModel, Field


# ---------- Agent 1 ----------
class CompetenceRequise(BaseModel):
    nom: str
    niveau: str = Field(description="obligatoire | souhaitee")
    poids: int = Field(description="Importance de 1 à 5")


class GrillePonderation(BaseModel):
    competences: int
    experience: int
    formation: int
    langues: int = Field(description="Le total des 4 poids vaut 100")


class AnalyseOffre(BaseModel):
    resume_poste: str
    seniorite: str = Field(description="junior | confirme | senior | expert")
    experience_min_annees: int
    competences: List[CompetenceRequise]
    formation_requise: str
    langues: List[str]
    soft_skills: List[str]
    criteres_eliminatoires: List[str]
    grille_ponderation: GrillePonderation
    alertes_biais: List[str]


# ---------- Agent 2 ----------
class EvaluationCandidat(BaseModel):
    candidat_id: str = Field(description="Identifiant anonyme, ex. C01")
    score_competences: float
    score_experience: float
    score_formation: float
    score_langues: float
    score_global: float
    competences_trouvees: List[str]
    competences_manquantes: List[str]
    points_forts: List[str]
    points_vigilance: List[str]
    justification: str
    recommandation: str = Field(description="forte | moyenne | faible")


class EvaluationsLot(BaseModel):
    evaluations: List[EvaluationCandidat]


# ---------- Agent 3 ----------
class QuestionPreQual(BaseModel):
    question: str
    objectif: str


class Questionnaire(BaseModel):
    candidat_id: str
    message_accueil: str
    questions: List[QuestionPreQual]


class QuestionnairesLot(BaseModel):
    questionnaires: List[Questionnaire]


# ---------- Agent 4 ----------
class PropositionEntretien(BaseModel):
    candidat_id: str
    creneau: str = Field(description="Créneau attribué, recopié depuis la liste fournie")
    type_entretien: str
    objet_email: str
    corps_email: str
    guide_entretien: List[str]
    statut: str = Field(description="Toujours : « À valider par un recruteur »")


class PlanningEntretiens(BaseModel):
    propositions: List[PropositionEntretien]
    remarques: str = Field(description="Chaîne vide si rien à signaler")
