#!/usr/bin/env python3
"""
Integrated Clinical Assessment & RAG Roadmap Generator
-------------------------------------------------------
Combines the Bayesian intake engine with RAG-based treatment recommendations.
Generates personalized roadmaps based on clinical assessment and evidence-based sources.
"""

import os
import json
import math
import csv
import time
from collections import OrderedDict
from glob import glob
from datetime import datetime
from pathlib import Path

# RAG imports
try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[Warning] RAG libraries not available. Install: pip install chromadb sentence-transformers")

# --- CONFIGURATION ---
DATA_FORMS_DIR = "data/forms"
LOG_CSV = "clinical_session_log.csv"
MAX_QUESTIONS = 15
CONFIDENCE_LOCK = 0.95 
RAG_OUTPUT_FILE = "rag_input.json"

# RAG Configuration
VECTOR_DB_PATH = "../../data/vector_db_mini"  # Use mini for faster queries
COLLECTION_NAME = "clinical_rag_mini"
MODEL_NAME = "all-mpnet-base-v2"
TOP_K = 8  # Number of relevant chunks to retrieve

PATHS = ["PATH_A", "PATH_B"]  # A=Anxiety, B=Depression

DOMAIN_MAP = {
    "PATH_A": "anxiety",
    "PATH_B": "depression"
}

# --- BAYESIAN LOGIC ---

def get_likelihood(answer_val, max_val, q_domain, target_path):
    """Returns P(Evidence | Hypothesis) using Non-Linear Logic"""
    target_domain = DOMAIN_MAP[target_path]
    
    p_hit = 0.0 
    if q_domain == target_domain:
        p_hit = 0.80
    elif (target_domain == "depression" and q_domain == "anxiety") or \
         (target_domain == "anxiety" and q_domain == "depression"):
        p_hit = 0.45
    else:
        p_hit = 0.15
        
    p_false_alarm = 0.12 if q_domain == target_domain else 0.08
    
    intensity = float(answer_val) / max_val
    
    p_evidence_given_true = (1.0 - p_hit) * (1.0 - intensity) + (p_hit * intensity)
    p_evidence_given_false = (1.0 - p_false_alarm) * (1.0 - intensity) + (p_false_alarm * intensity)

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
        
        p_e_given_h, p_e_given_not_h = get_likelihood(answer_val, max_val, qmeta["domain"], path)
        
        p_evidence = (p_e_given_h * current_p) + (p_e_given_not_h * (1 - current_p))
        if p_evidence == 0: p_evidence = 1e-9
        
        posterior = (p_e_given_h * current_p) / p_evidence
        posterior = max(0.05, min(0.95, posterior))
        
        new_priors[path] = posterior
    
    # Comorbidity adjustment
    if len(new_priors) == 2:
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

# --- UTILITIES ---

def entropy(prob):
    if prob <= 0 or prob >= 1: return 0
    return -prob * math.log2(prob) - (1 - prob) * math.log2(1 - prob)

def select_next_question(state, pool):
    unasked = [q for q in pool.values() if q["id"] not in state["answers"]]
    if not unasked: return None
    if state["risk_flags"]["suicidal"]: return None

    uncertain_paths = sorted(PATHS, key=lambda p: entropy(state["prob_paths"][p]), reverse=True)
    target_path = uncertain_paths[0]
    target_domain = DOMAIN_MAP[target_path]

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

        if form.get("initial_trauma_question"):
            continue
            
        for q in form.get("questions", []):
            qid = f"{form['id']}_{q['id']}"
            question_domain = q.get("domain", form_domain)
            
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
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"{p} ({DOMAIN_MAP[p].capitalize()}): {bar} {probs[p]*100:.1f}%")
    print("-"*30 + "\n")

# --- RAG INTEGRATION ---

def calculate_severity(probability):
    """Maps probability to severity level"""
    if probability < 0.3:
        return "Low"
    elif probability < 0.7:
        return "Moderate"
    else:
        return "High"

def generate_rag_query(anxiety_prob, depression_prob, anxiety_severity, depression_severity, comorbidity):
    """Generates optimized query for RAG system"""
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

def query_rag_system(query_string, top_k=TOP_K):
    """Queries the RAG vector store and returns relevant chunks"""
    if not RAG_AVAILABLE:
        print("\n[Error] RAG libraries not available. Cannot retrieve recommendations.")
        return []
    
    try:
        print(f"\n{'='*70}")
        print("QUERYING CLINICAL KNOWLEDGE BASE")
        print('='*70)
        print(f"Query: {query_string}")
        print(f"Retrieving top {top_k} relevant sources...")
        
        # Initialize
        client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        collection = client.get_collection(name=COLLECTION_NAME)
        model = SentenceTransformer(MODEL_NAME)
        
        # Encode query
        query_embedding = model.encode([query_string])
        
        # Search
        results = collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        chunks = []
        print(f"\nRetrieved {len(results['documents'][0])} relevant excerpts:\n")
        
        for i, (doc, meta, dist) in enumerate(zip(
            results['documents'][0], 
            results['metadatas'][0], 
            results['distances'][0]
        ), 1):
            similarity = (1 - dist) * 100
            
            chunk_data = {
                'rank': i,
                'text': doc,
                'source': meta.get('source_file', 'Unknown'),
                'pages': meta.get('page_numbers', '?'),
                'section': meta.get('header', 'Section'),
                'similarity': similarity
            }
            chunks.append(chunk_data)
            
            print(f"[{i}] {chunk_data['source']} (Pages: {chunk_data['pages']})")
            print(f"    Section: {chunk_data['section']}")
            print(f"    Similarity: {similarity:.1f}%")
            print(f"    Preview: {doc[:150]}...\n")
        
        return chunks
        
    except Exception as e:
        print(f"\n[Error] RAG query failed: {e}")
        return []

def generate_roadmap(state, chunks):
    """Generates personalized treatment roadmap from assessment and RAG results"""
    anxiety_prob = state["prob_paths"]["PATH_A"]
    depression_prob = state["prob_paths"]["PATH_B"]
    
    anxiety_severity = calculate_severity(anxiety_prob)
    depression_severity = calculate_severity(depression_prob)
    comorbidity = anxiety_prob > 0.5 and depression_prob > 0.5
    
    print(f"\n{'='*70}")
    print("PERSONALIZED TREATMENT ROADMAP")
    print('='*70)
    
    # Clinical Profile
    print("\n📋 CLINICAL PROFILE")
    print("-" * 70)
    print(f"Anxiety Assessment:    {anxiety_prob:.2f} ({anxiety_severity} Severity)")
    print(f"Depression Assessment: {depression_prob:.2f} ({depression_severity} Severity)")
    if comorbidity:
        print(f"⚠️  Comorbidity Detected: Yes (Co-occurring conditions)")
    else:
        print(f"Comorbidity Detected: No")
    
    if state["risk_flags"]["suicidal"]:
        print(f"\n🚨 CRITICAL: Suicidal ideation detected - Immediate intervention required")
    
    # Primary Focus
    print(f"\n🎯 PRIMARY FOCUS AREAS")
    print("-" * 70)
    focus_areas = []
    if anxiety_prob > 0.5:
        focus_areas.append(f"• Anxiety Management ({anxiety_severity} priority)")
    if depression_prob > 0.5:
        focus_areas.append(f"• Depression Treatment ({depression_severity} priority)")
    if not focus_areas:
        focus_areas.append("• General Mental Wellness & Prevention")
    
    for area in focus_areas:
        print(area)
    
    # Evidence-Based Recommendations
    print(f"\n📚 EVIDENCE-BASED RECOMMENDATIONS")
    print("-" * 70)
    print("Based on clinical psychology literature:\n")
    
    if chunks:
        # Group chunks by source
        source_recommendations = {}
        for chunk in chunks[:5]:  # Top 5 most relevant
            source = chunk['source']
            if source not in source_recommendations:
                source_recommendations[source] = []
            source_recommendations[source].append(chunk)
        
        for idx, (source, source_chunks) in enumerate(source_recommendations.items(), 1):
            print(f"{idx}. From '{source}':")
            # Take the most relevant chunk from this source
            best_chunk = max(source_chunks, key=lambda x: x['similarity'])
            print(f"   Section: {best_chunk['section']} (Pages: {best_chunk['pages']})")
            print(f"   Key Insight: {best_chunk['text'][:300]}...")
            print()
    else:
        print("⚠️  No RAG results available. Using general recommendations.")
    
    # Treatment Recommendations
    print(f"\n💊 RECOMMENDED INTERVENTIONS")
    print("-" * 70)
    
    if comorbidity:
        print("• Integrated CBT addressing both anxiety and depression")
        print("• Behavioral activation combined with anxiety management")
        print("• Consider medication evaluation for dual diagnosis")
    elif anxiety_prob > 0.5:
        if anxiety_severity == "High":
            print("• Intensive CBT for anxiety (2x per week recommended)")
            print("• Exposure therapy for avoidance behaviors")
            print("• Consider medication consultation")
        else:
            print("• Standard CBT for anxiety (weekly sessions)")
            print("• Relaxation training and mindfulness")
            print("• Worry management techniques")
    elif depression_prob > 0.5:
        if depression_severity == "High":
            print("• Intensive CBT for depression (2x per week recommended)")
            print("• Behavioral activation protocol")
            print("• Consider medication evaluation")
        else:
            print("• Standard CBT for depression (weekly sessions)")
            print("• Activity scheduling and monitoring")
            print("• Cognitive restructuring exercises")
    else:
        print("• Preventive mental health strategies")
        print("• Self-care and wellness practices")
        print("• Stress management techniques")
    
    # Short-term Tasks (0-4 weeks)
    print(f"\n📅 SHORT-TERM TASKS (Next 4 Weeks)")
    print("-" * 70)
    tasks = []
    
    if anxiety_prob > 0.5:
        tasks.extend([
            "Week 1: Begin thought monitoring for anxious thoughts",
            "Week 2: Practice progressive muscle relaxation daily",
            "Week 3: Identify and challenge worry patterns",
            "Week 4: Start gradual exposure to avoided situations"
        ])
    
    if depression_prob > 0.5:
        tasks.extend([
            "Week 1: Create daily activity schedule",
            "Week 2: Identify and engage in 3 pleasurable activities",
            "Week 3: Challenge negative automatic thoughts",
            "Week 4: Increase social connections (1-2 interactions)"
        ])
    
    if not tasks:
        tasks.extend([
            "Week 1: Establish consistent sleep schedule",
            "Week 2: Begin daily mindfulness practice (10 min)",
            "Week 3: Develop stress management routine",
            "Week 4: Build social support network"
        ])
    
    for task in tasks[:4]:  # Limit to 4 tasks
        print(f"• {task}")
    
    # Long-term Goals (1-3 months)
    print(f"\n🎯 LONG-TERM GOALS (1-3 Months)")
    print("-" * 70)
    
    if comorbidity:
        print("• Achieve symptom reduction in both anxiety and depression")
        print("• Develop integrated coping skills toolkit")
        print("• Establish sustainable self-care routines")
    elif anxiety_prob > 0.5:
        print("• Reduce anxiety symptoms by 50% or more")
        print("• Build confidence in managing worry and stress")
        print("• Resume avoided activities and situations")
    elif depression_prob > 0.5:
        print("• Improve mood and energy levels significantly")
        print("• Re-engage in meaningful activities and relationships")
        print("• Develop healthy behavioral activation patterns")
    else:
        print("• Maintain mental wellness and prevent symptom emergence")
        print("• Build resilience and coping skills")
        print("• Optimize overall life satisfaction")
    
    # Next Steps
    print(f"\n🚀 NEXT STEPS")
    print("-" * 70)
    if state["risk_flags"]["suicidal"]:
        print("1. ⚠️  IMMEDIATE: Contact crisis hotline or emergency services")
        print("2. Schedule emergency psychiatric evaluation")
        print("3. Ensure safety planning with support person")
    else:
        print("1. Schedule intake appointment with licensed therapist")
        print("2. Consider psychiatric evaluation if symptoms are severe")
        print("3. Begin tracking symptoms daily (mood, anxiety, sleep)")
        print("4. Share this roadmap with your mental health provider")
    
    print(f"\n{'='*70}")
    print("End of Roadmap - Stay committed to your mental health journey!")
    print('='*70)
    
    # Save roadmap to file
    roadmap_data = {
        "timestamp": datetime.now().isoformat(),
        "clinical_profile": {
            "anxiety": {"probability": anxiety_prob, "severity": anxiety_severity},
            "depression": {"probability": depression_prob, "severity": depression_severity},
            "comorbidity": comorbidity
        },
        "risk_flags": state["risk_flags"],
        "focus_areas": focus_areas,
        "evidence_sources": [{"source": c['source'], "section": c['section']} for c in chunks[:5]],
        "short_term_tasks": tasks[:4],
        "roadmap_generated": True
    }
    
    with open("treatment_roadmap.json", "w", encoding="utf-8") as f:
        json.dump(roadmap_data, f, indent=2)
    
    print("\n📄 Roadmap saved to: treatment_roadmap.json")

# --- MAIN INTEGRATED SYSTEM ---

def run_integrated_system():
    """Main function that runs the complete integrated system"""
    print("="*70)
    print("INTEGRATED CLINICAL ASSESSMENT & RAG SYSTEM")
    print("="*70)
    print("\nThis system will:")
    print("1. Conduct adaptive clinical assessment (Bayesian inference)")
    print("2. Query clinical psychology knowledge base (RAG)")
    print("3. Generate personalized treatment roadmap")
    print("\n" + "="*70 + "\n")
    
    # Check RAG availability
    if not RAG_AVAILABLE:
        print("⚠️  RAG system unavailable - will proceed with assessment only")
        print("   Install libraries: pip install chromadb sentence-transformers\n")
    
    # Load forms
    forms = load_forms()
    if not forms:
        print("[Error] No clinical forms found. Check data/forms/ directory.")
        return
    
    pool = build_question_pool(forms)
    print(f"[System] Loaded {len(pool)} clinical questions\n")
    
    # Initialize state
    state = {
        "answers": {},
        "prob_paths": {p: 0.20 for p in PATHS}, 
        "risk_flags": {"suicidal": False},
    }
    
    # PHASE 1: Clinical Assessment
    print("="*70)
    print("PHASE 1: CLINICAL ASSESSMENT")
    print("="*70 + "\n")
    
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
            print("\n" + "!"*40)
            print("CRITICAL ALERT: Suicidal Risk Detected")
            print("!"*40)
            break
            
        state["prob_paths"] = bayes_update_independent(state["prob_paths"], q, ans)
        print_status(state["prob_paths"])
        step += 1
    
    # Assessment Summary
    print("\n" + "="*70)
    print("ASSESSMENT COMPLETE")
    print("="*70)
    
    anxiety_prob = state["prob_paths"]["PATH_A"]
    depression_prob = state["prob_paths"]["PATH_B"]
    anxiety_severity = calculate_severity(anxiety_prob)
    depression_severity = calculate_severity(depression_prob)
    comorbidity = anxiety_prob > 0.5 and depression_prob > 0.5
    
    print(f"\nAnxiety:    {anxiety_prob:.2f} ({anxiety_severity})")
    print(f"Depression: {depression_prob:.2f} ({depression_severity})")
    if comorbidity:
        print(f"Comorbidity: Yes")
    
    # PHASE 2: RAG Query
    if RAG_AVAILABLE and os.path.exists(VECTOR_DB_PATH):
        query_string = generate_rag_query(
            anxiety_prob, depression_prob,
            anxiety_severity, depression_severity, comorbidity
        )
        
        chunks = query_rag_system(query_string)
    else:
        print("\n⚠️  Skipping RAG query (system unavailable or vector DB not found)")
        chunks = []
    
    # PHASE 3: Generate Roadmap
    generate_roadmap(state, chunks)
    
    # Log session
    with open(LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.time(), 
            json.dumps(state["prob_paths"]), 
            state["risk_flags"]["suicidal"],
            len(chunks)
        ])
    
    print("\n✅ Session logged to:", LOG_CSV)

if __name__ == "__main__":
    run_integrated_system()
