"""
Bayesian Assessment Logic - Extracted from interactive_intake.py
"""
import math
from typing import Dict

PATHS = ["PATH_A", "PATH_B"]  # A=Anxiety, B=Depression

DOMAIN_MAP = {
    "PATH_A": "anxiety",
    "PATH_B": "depression"
}

def get_likelihood(answer_val: int, max_val: int, q_domain: str, target_path: str):
    """
    Returns P(Evidence | Hypothesis) using Non-Linear Logic
    """
    target_domain = DOMAIN_MAP[target_path]
    
    # Define sensitivity
    if q_domain == target_domain:
        p_hit = 0.80
    elif (target_domain == "depression" and q_domain == "anxiety") or \
         (target_domain == "anxiety" and q_domain == "depression"):
        p_hit = 0.45
    else:
        p_hit = 0.15
    
    # Define false positive rate
    p_false_alarm = 0.12 if q_domain == target_domain else 0.08
    
    # Interpolate based on answer intensity
    intensity = float(answer_val) / max_val
    
    p_evidence_given_true = (1.0 - p_hit) * (1.0 - intensity) + (p_hit * intensity)
    p_evidence_given_false = (1.0 - p_false_alarm) * (1.0 - intensity) + (p_false_alarm * intensity)
    
    # Safety clamp
    p_evidence_given_true = max(0.001, p_evidence_given_true)
    p_evidence_given_false = max(0.001, p_evidence_given_false)
    
    return p_evidence_given_true, p_evidence_given_false

def bayes_update(priors: Dict[str, float], q_domain: str, answer_val: int, max_val: int = 3) -> Dict[str, float]:
    """
    Update probabilities using Bayes' theorem
    """
    new_priors = {}
    
    for path in PATHS:
        current_p = priors[path]
        
        # Get P(E|H) and P(E|~H)
        p_e_given_h, p_e_given_not_h = get_likelihood(answer_val, max_val, q_domain, path)
        
        # Marginal Likelihood P(E)
        p_evidence = (p_e_given_h * current_p) + (p_e_given_not_h * (1 - current_p))
        if p_evidence == 0:
            p_evidence = 1e-9
        
        # Bayes Rule
        posterior = (p_e_given_h * current_p) / p_evidence
        
        # Clamping
        posterior = max(0.05, min(0.95, posterior))
        
        new_priors[path] = posterior
    
    # Comorbidity adjustment
    anxiety_p = new_priors["PATH_A"]
    depression_p = new_priors["PATH_B"]
    
    if anxiety_p > 0.3 and depression_p > 0.3:
        anxiety_increased = anxiety_p > priors["PATH_A"]
        depression_increased = depression_p > priors["PATH_B"]
        
        if anxiety_increased and depression_increased:
            boost = 0.05
            new_priors["PATH_A"] = min(0.95, anxiety_p * (1 + boost))
            new_priors["PATH_B"] = min(0.95, depression_p * (1 + boost))
    
    return new_priors

def calculate_severity(probability: float) -> str:
    """Maps probability to severity level"""
    if probability < 0.3:
        return "Low"
    elif probability < 0.7:
        return "Moderate"
    else:
        return "High"

def generate_rag_query(anxiety_prob: float, depression_prob: float) -> str:
    """Generate RAG query string based on probabilities"""
    anxiety_severity = calculate_severity(anxiety_prob)
    depression_severity = calculate_severity(depression_prob)
    comorbidity = anxiety_prob > 0.5 and depression_prob > 0.5
    
    query_parts = []
    
    if comorbidity:
        query_parts.append("treatment for comorbid anxiety and depression")
        query_parts.append("managing co-occurring anxiety and depression")
        
        if anxiety_severity == "High" or depression_severity == "High":
            query_parts.append("severe comorbid mental health treatment")
    elif anxiety_prob > 0.5:
        query_parts.append("cognitive behavioral therapy for anxiety")
        query_parts.append("anxiety management techniques")
        
        if anxiety_severity == "High":
            query_parts.append("severe anxiety treatment strategies")
        query_parts.append("generalized anxiety disorder interventions")
    elif depression_prob > 0.5:
        query_parts.append("cognitive behavioral therapy for depression")
        query_parts.append("depression treatment approaches")
        
        if depression_severity == "High":
            query_parts.append("severe depression treatment interventions")
        query_parts.append("major depressive disorder therapy")
    else:
        query_parts.append("mental wellness strategies")
        query_parts.append("preventive mental health approaches")
    
    return " ".join(query_parts)

def run_assessment(answers: Dict[str, int]) -> Dict:
    """
    Run Bayesian assessment on answers
    
    Args:
        answers: Dict of question_id -> answer_value (0-3)
        
    Returns:
        Dict with anxiety_prob, depression_prob, severity, query
    """
    # Initialize priors
    priors = {"PATH_A": 0.20, "PATH_B": 0.20}
    
    # Process each answer
    for qid, answer_val in answers.items():
        # Determine question domain from ID
        if "gad" in qid.lower():
            q_domain = "anxiety"
        elif "phq" in qid.lower():
            q_domain = "depression"
        else:
            q_domain = "general"
        
        # Update probabilities
        priors = bayes_update(priors, q_domain, answer_val)
    
    anxiety_prob = priors["PATH_A"]
    depression_prob = priors["PATH_B"]
    
    return {
        "anxiety_probability": anxiety_prob,
        "depression_probability": depression_prob,
        "anxiety_severity": calculate_severity(anxiety_prob),
        "depression_severity": calculate_severity(depression_prob),
        "comorbidity": anxiety_prob > 0.5 and depression_prob > 0.5,
        "query": generate_rag_query(anxiety_prob, depression_prob)
    }
