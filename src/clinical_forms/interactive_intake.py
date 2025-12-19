#!/usr/bin/env python3
"""
Real-World Mental Health Intake Engine (Bayesian Multi-Label)
------------------------------------------------------------
v5 Updates:
- Removed PTSD/Trauma support - focus on Anxiety and Depression only
- Improved Bayesian probability logic for better cross-domain relationships
- Enhanced comorbidity detection
- Added RAG integration interface for roadmap generation
"""

import os
import json
import math
import csv
import time
from collections import OrderedDict
from glob import glob
from datetime import datetime

# --- CONFIGURATION ---
DATA_FORMS_DIR = "data/forms"
LOG_CSV = "clinical_session_log.csv"
MAX_QUESTIONS = 15
CONFIDENCE_LOCK = 0.95 
RAG_OUTPUT_FILE = "rag_input.json"

PATHS = ["PATH_A", "PATH_B"]  # A=Anxiety, B=Depression

DOMAIN_MAP = {
    "PATH_A": "anxiety",
    "PATH_B": "depression"
}

# --- CORE LOGIC: PROBABILITIES ---

def get_likelihood(answer_val, max_val, q_domain, target_path):
    """
    Returns P(Evidence | Hypothesis) using Non-Linear Logic.
    Improved for better cross-domain relationships and comorbidity detection.
    """
    target_domain = DOMAIN_MAP[target_path]
    
    # 1. Define Sensitivity (How likely is a positive answer if sick?)
    # More conservative values to prevent overconfidence
    p_hit = 0.0 
    
    if q_domain == target_domain:
        # Direct symptoms: moderate-high sensitivity (reduced from 0.90 to prevent overconfidence)
        p_hit = 0.80
    elif (target_domain == "depression" and q_domain == "anxiety") or \
         (target_domain == "anxiety" and q_domain == "depression"):
        # Cross-domain: moderate correlation for comorbidity
        p_hit = 0.45
    else:
        # Unrelated domains: low correlation
        p_hit = 0.15
        
    # 2. Define False Positive Rate (How likely is a positive answer if healthy?)
    # Healthy people answer 'No' (0) most of the time.
    p_false_alarm = 0.12 if q_domain == target_domain else 0.08
    
    # 3. Interpolate based on answer intensity (0 to 1 scale)
    intensity = float(answer_val) / max_val # 0.0 to 1.0
    
    # P(Evidence | SICK)
    # If Sick: We expect intensity=1.0. If we see 0, it's a 'miss'.
    # Interpolate between (1 - p_hit) and (p_hit)
    p_evidence_given_true = (1.0 - p_hit) * (1.0 - intensity) + (p_hit * intensity)
    
    # P(Evidence | HEALTHY)
    # If Healthy: We expect intensity=0.0. If we see 1, it's a 'false alarm'.
    # Interpolate between (1 - p_false_alarm) and (p_false_alarm)
    # FIXED: The previous version forced this to 0 if intensity was 1.0.
    p_evidence_given_false = (1.0 - p_false_alarm) * (1.0 - intensity) + (p_false_alarm * intensity)

    # Safety clamp
    p_evidence_given_true = max(0.001, p_evidence_given_true)
    p_evidence_given_false = max(0.001, p_evidence_given_false)
    
    return p_evidence_given_true, p_evidence_given_false

def bayes_update_independent(priors, qmeta, answer_val):
    max_val = 3.0
    if qmeta.get("options"):
        vals = [opt["value"] for opt in qmeta["options"]]
        if vals: max_val = max(vals)
    
    new_priors = {}
    
    for path in PATHS:
        current_p = priors[path]
        
        # Get P(E|H) and P(E|~H)
        p_e_given_h, p_e_given_not_h = get_likelihood(answer_val, max_val, qmeta["domain"], path)
        
        # Marginal Likelihood P(E)
        p_evidence = (p_e_given_h * current_p) + (p_e_given_not_h * (1 - current_p))
        
        if p_evidence == 0: p_evidence = 1e-9
        
        # Bayes Rule
        posterior = (p_e_given_h * current_p) / p_evidence
        
        # CLAMPING: Softer bounds to prevent overconfidence (0.05 to 0.95)
        posterior = max(0.05, min(0.95, posterior))
        
        new_priors[path] = posterior
    
    # Comorbidity adjustment: if both probabilities are rising, slightly boost both
    # This helps detect comorbidity better
    if len(new_priors) == 2:
        anxiety_p = new_priors["PATH_A"]
        depression_p = new_priors["PATH_B"]
        
        # If both are above 0.3 and rising, apply small comorbidity boost
        if anxiety_p > 0.3 and depression_p > 0.3:
            # Check if both increased from priors
            anxiety_increased = anxiety_p > priors["PATH_A"]
            depression_increased = depression_p > priors["PATH_B"]
            
            if anxiety_increased and depression_increased:
                # Small boost (5% of current value) to both
                boost = 0.05
                new_priors["PATH_A"] = min(0.95, anxiety_p * (1 + boost))
                new_priors["PATH_B"] = min(0.95, depression_p * (1 + boost))
        
    return new_priors

# --- UTILITIES ---

def entropy(prob):
    if prob <= 0 or prob >= 1: return 0
    return -prob * math.log2(prob) - (1 - prob) * math.log2(1 - prob)

def select_next_question(state, pool):
    unasked = [q for q in pool.values() if q["id"] not in state["answers"]]
    if not unasked: return None
    if state["risk_flags"]["suicidal"]: return None

    # Sort paths by uncertainty (Entropy)
    uncertain_paths = sorted(PATHS, key=lambda p: entropy(state["prob_paths"][p]), reverse=True)
    target_path = uncertain_paths[0]
    target_domain = DOMAIN_MAP[target_path]

    # Prioritize questions for the most uncertain path
    relevant_questions = [q for q in unasked if q["domain"] == target_domain]
    
    if relevant_questions:
        return relevant_questions[0]
    
    return unasked[0]

def load_forms(folder=DATA_FORMS_DIR):
    if not os.path.exists(folder):
        return []
    files = glob(os.path.join(folder, "*.json"))
    forms = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                forms.append(json.load(fh))
        except Exception as e:
            print(f"[Error] Could not load {f}: {e}")
    return forms

def build_question_pool(forms):
    pool = OrderedDict()
    for form in forms:
        form_domain = "general"
        fid_upper = form.get("id", "").upper()
        if "GAD" in fid_upper: form_domain = "anxiety"
        if "PHQ" in fid_upper: form_domain = "depression"
        # PTSD forms are ignored - trauma support removed

        # Skip trauma-related questions
        if form.get("initial_trauma_question"):
            continue  # Skip trauma questions
            
        for q in form.get("questions", []):
            qid = f"{form['id']}_{q['id']}"
            question_domain = q.get("domain", form_domain)
            
            # Filter out trauma domain questions
            if question_domain == "trauma":
                continue
                
            pool[qid] = {
                "id": qid, "text": q["text"], 
                "domain": question_domain,
                "options": q.get("options") or form.get("options_scale"),
                "risk_flag": q.get("risk_flag", False), "source": form["id"]
            }
    return pool

def get_user_input(options):
    valid_values = [str(o["value"]) for o in options]
    print("\nOptions:")
    for o in options:
        print(f"  [{o['value']}] {o['label']}")
        
    while True:
        ans = input("Your Answer > ").strip().lower()
        if ans in valid_values: return int(ans)
        for o in options:
            if ans in o["label"].lower(): return o["value"]
        if ans in ['y', 'yes', 'true']: return 1
        if ans in ['n', 'no', 'false']: return 0
        print("Invalid input.")

def print_status(probs):
    print("\n" + "-"*30)
    print("Current Clinical Hypothesis:")
    for p in PATHS:
        bar_len = int(probs[p] * 20)
        bar = "#" * bar_len + "-" * (20 - bar_len)
        print(f"{p} ({DOMAIN_MAP[p].capitalize()}): {bar} {probs[p]*100:.1f}%")
    print("-"*30 + "\n")

def run_interactive():
    print("Initializing Clinical Intake Engine (v4 - Final)...")
    forms = load_forms()
    if not forms: return

    pool = build_question_pool(forms)
    print(f"[System] Loaded {len(pool)} questions.")
    
    state = {
        "answers": {},
        "prob_paths": {p: 0.20 for p in PATHS}, 
        "risk_flags": {"suicidal": False},
    }
    
    step = 0
    while step < MAX_QUESTIONS:
        uncertain = [p for p in PATHS if 0.10 < state["prob_paths"][p] < 0.90]
        if not uncertain and step > 5:
            print("\n[System] Sufficient clinical confidence reached.")
            break
            
        q = select_next_question(state, pool)
        if not q: break
        
        print(f"\n[Q{step+1}] {q['text']}")
        time.sleep(0.3) 
        ans = get_user_input(q["options"])
        
        state["answers"][q["id"]] = ans
        
        if q.get("risk_flag") and ans > 0:
            state["risk_flags"]["suicidal"] = True
            print("\n" + "!"*40 + "\nCRITICAL ALERT: Risk Protocol Initiated.\n" + "!"*40)
            break
            
        state["prob_paths"] = bayes_update_independent(state["prob_paths"], q, ans)
        print_status(state["prob_paths"])
        step += 1

    print("\n=== FINAL CLINICAL PROFILE ===")
    final_profile = []
    for p in PATHS:
        pct = state["prob_paths"][p]
        status = "Low"
        if pct > 0.5: status = "Moderate"
        if pct > 0.8: status = "High"
        print(f"Diagnosis: {DOMAIN_MAP[p].capitalize():<12} | Probability: {pct:.2f} | Severity: {status}")
        if pct > 0.5: final_profile.append(DOMAIN_MAP[p])
            
    print(f"\nRecommended Roadmap Focus: {', '.join(final_profile).upper() if final_profile else 'GENERAL WELLNESS'}")
    
    # Prepare RAG integration data
    try:
        from rag_data_preparer import prepare_rag_input
        
        rag_data = prepare_rag_input(
            anxiety_prob=state["prob_paths"]["PATH_A"],
            depression_prob=state["prob_paths"]["PATH_B"],
            answers=state["answers"],
            question_pool=pool,
            risk_flags=state["risk_flags"]
        )
        
        # Save RAG input to JSON file
        with open(RAG_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(rag_data, f, indent=2, ensure_ascii=False)
        
        print("\n=== RAG INTEGRATION DATA PREPARED ===")
        print(f"Anxiety Probability: {rag_data['probabilities']['anxiety']:.2f} (Severity: {rag_data['severity']['anxiety']})")
        print(f"Depression Probability: {rag_data['probabilities']['depression']:.2f} (Severity: {rag_data['severity']['depression']})")
        print(f"Comorbidity Detected: {'Yes' if rag_data['comorbidity'] else 'No'}")
        print(f"\nRAG Query String: \"{rag_data['query_string']}\"")
        print(f"\nRAG Configuration:")
        print(f"  Collection: {rag_data['rag_config']['collection_name']}")
        print(f"  Model: {rag_data['rag_config']['model_name']}")
        print(f"  Vector DB: {rag_data['rag_config']['vector_db_path']}")
        print(f"  Top K: {rag_data['rag_config']['top_k']}")
        print(f"\n[Structured data saved to {RAG_OUTPUT_FILE}]")
        print("[Ready to send to RAG system (knowledge-base)]")
    except ImportError:
        print("\n[Note] RAG data preparation module not found. Skipping RAG integration.")
    except Exception as e:
        print(f"\n[Warning] Error preparing RAG data: {e}")
    
    with open(LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([time.time(), json.dumps(state["prob_paths"]), state["risk_flags"]["suicidal"]])

if __name__ == "__main__":
    run_interactive()