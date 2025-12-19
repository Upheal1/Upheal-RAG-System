#!/usr/bin/env python3
"""
RAG Data Preparation Interface
--------------------------------
Prepares structured assessment data for RAG system integration (knowledge-base).
This module does NOT implement actual RAG querying - it only prepares the data
structure and query string that will be sent to the RAG system externally.
"""

import json
from datetime import datetime
from typing import Dict, List, Any


def calculate_severity(probability: float) -> str:
    """
    Maps probability to severity level.
    
    Args:
        probability: Float between 0.0 and 1.0
        
    Returns:
        "Low", "Moderate", or "High"
    """
    if probability < 0.3:
        return "Low"
    elif probability < 0.7:
        return "Moderate"
    else:
        return "High"


def generate_rag_query_string(
    anxiety_prob: float,
    depression_prob: float,
    anxiety_severity: str,
    depression_severity: str,
    comorbidity: bool
) -> str:
    """
    Constructs optimized query string based on probabilities, severity, and symptoms.
    Query is natural language optimized for clinical psychology knowledge base.
    
    Args:
        anxiety_prob: Probability of anxiety (0.0 to 1.0)
        depression_prob: Probability of depression (0.0 to 1.0)
        anxiety_severity: "Low", "Moderate", or "High"
        depression_severity: "Low", "Moderate", or "High"
        comorbidity: True if both probabilities > 0.5
        
    Returns:
        Formatted query string optimized for semantic search
    """
    query_parts = []
    
    if comorbidity:
        # Comorbidity case: both anxiety and depression
        query_parts.append("treatment for comorbid anxiety and depression")
        query_parts.append("dual diagnosis")
        query_parts.append("co-occurring anxiety and depression")
        
        # Add severity information
        if anxiety_severity == "High" or depression_severity == "High":
            query_parts.append("severe comorbid mental health treatment")
        elif anxiety_severity == "Moderate" or depression_severity == "Moderate":
            query_parts.append("moderate comorbid anxiety and depression therapy")
    elif anxiety_prob > 0.5:
        # Anxiety-focused case
        query_parts.append("treatment for generalized anxiety disorder")
        
        # Add severity-specific terms
        if anxiety_severity == "High":
            query_parts.append("severe anxiety management techniques")
            query_parts.append("intensive anxiety treatment")
        elif anxiety_severity == "Moderate":
            query_parts.append("moderate anxiety therapy approaches")
        else:
            query_parts.append("mild anxiety management strategies")
        
        query_parts.append("anxiety management techniques")
        query_parts.append("worry reduction strategies")
        query_parts.append("anxiety coping skills")
    elif depression_prob > 0.5:
        # Depression-focused case
        query_parts.append("treatment for major depressive disorder")
        
        # Add severity-specific terms
        if depression_severity == "High":
            query_parts.append("severe depression treatment approaches")
            query_parts.append("intensive depression therapy")
        elif depression_severity == "Moderate":
            query_parts.append("moderate depression therapy interventions")
        else:
            query_parts.append("mild depression management strategies")
        
        query_parts.append("depression therapy approaches")
        query_parts.append("mood improvement strategies")
        query_parts.append("depression coping techniques")
    else:
        # Low probabilities: general wellness
        query_parts.append("general mental health wellness")
        query_parts.append("preventive mental health strategies")
        query_parts.append("mental health maintenance")
        query_parts.append("wellness and self-care practices")
    
    # Combine into natural language query
    query = " ".join(query_parts)
    return query


def prepare_rag_input(
    anxiety_prob: float,
    depression_prob: float,
    answers: Dict[str, int],
    question_pool: Dict[str, Any],
    risk_flags: Dict[str, bool]
) -> Dict[str, Any]:
    """
    Prepares structured assessment data for RAG system integration.
    
    Args:
        anxiety_prob: Final probability for anxiety (0.0 to 1.0)
        depression_prob: Final probability for depression (0.0 to 1.0)
        answers: Dictionary mapping question IDs to answer values
        question_pool: Dictionary of all questions with metadata
        risk_flags: Dictionary of risk flags (e.g., {"suicidal": bool})
        
    Returns:
        Structured dictionary ready for RAG system
    """
    # Calculate severity levels
    anxiety_severity = calculate_severity(anxiety_prob)
    depression_severity = calculate_severity(depression_prob)
    comorbidity = anxiety_prob > 0.5 and depression_prob > 0.5
    
    # Generate query string
    query_string = generate_rag_query_string(
        anxiety_prob, depression_prob,
        anxiety_severity, depression_severity, comorbidity
    )
    
    # Extract symptom summaries
    anxiety_symptoms = []
    depression_symptoms = []
    anxiety_total = 0
    depression_total = 0
    
    for qid, answer_val in answers.items():
        # Find question in pool
        question = question_pool.get(qid)
        if not question:
            continue
        
        domain = question.get("domain", "general")
        question_text = question.get("text", "")
        
        symptom_entry = f"{question_text} (Score: {answer_val})"
        
        if domain == "anxiety":
            anxiety_symptoms.append(symptom_entry)
            anxiety_total += answer_val
        elif domain == "depression":
            depression_symptoms.append(symptom_entry)
            depression_total += answer_val
    
    # Build structured data
    rag_data = {
        "probabilities": {
            "anxiety": round(anxiety_prob, 4),
            "depression": round(depression_prob, 4)
        },
        "severity": {
            "anxiety": anxiety_severity,
            "depression": depression_severity
        },
        "comorbidity": comorbidity,
        "query_string": query_string,
        "symptom_summary": {
            "anxiety_symptoms": anxiety_symptoms,
            "depression_symptoms": depression_symptoms,
            "severity_scores": {
                "anxiety_total": anxiety_total,  # 0-21 for GAD-7
                "depression_total": depression_total  # 0-27 for PHQ-9
            }
        },
        "rag_config": {
            "collection_name": "clinical_psychology_rag",
            "model_name": "all-mpnet-base-v2",
            "vector_db_path": "../../data/vector_db_mini",  # Relative path from clinical_forms folder
            "top_k": 5  # Number of chunks to retrieve
        },
        "metadata": {
            "total_questions": len(answers),
            "assessment_timestamp": datetime.now().isoformat(),
            "risk_flags": risk_flags,
            "question_ids": list(answers.keys())
        }
    }
    
    return rag_data

