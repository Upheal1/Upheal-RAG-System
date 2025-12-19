"""
Interactive API Test - Simulates Real Website User Flow
This script asks you questions (like the website would), then sends your answers to the API
"""
import requests
import json
import os
import sys

# Add clinical_forms to path to import form loader
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'clinical_forms'))

# API base URL
BASE_URL = "http://localhost:8000"

# Simple hardcoded questions (GAD-7 + PHQ-9)
QUESTIONS = [
    # GAD-7 (Anxiety)
    {"id": "gad7_q1", "text": "Feeling nervous, anxious, or on edge", "domain": "anxiety"},
    {"id": "gad7_q2", "text": "Not being able to stop or control worrying", "domain": "anxiety"},
    {"id": "gad7_q3", "text": "Worrying too much about different things", "domain": "anxiety"},
    {"id": "gad7_q4", "text": "Trouble relaxing", "domain": "anxiety"},
    {"id": "gad7_q5", "text": "Being so restless that it's hard to sit still", "domain": "anxiety"},
    {"id": "gad7_q6", "text": "Becoming easily annoyed or irritable", "domain": "anxiety"},
    {"id": "gad7_q7", "text": "Feeling afraid as if something awful might happen", "domain": "anxiety"},
    
    # PHQ-9 (Depression)
    {"id": "phq9_q1", "text": "Little interest or pleasure in doing things", "domain": "depression"},
    {"id": "phq9_q2", "text": "Feeling down, depressed, or hopeless", "domain": "depression"},
    {"id": "phq9_q3", "text": "Trouble falling or staying asleep, or sleeping too much", "domain": "depression"},
    {"id": "phq9_q4", "text": "Feeling tired or having little energy", "domain": "depression"},
    {"id": "phq9_q5", "text": "Poor appetite or overeating", "domain": "depression"},
    {"id": "phq9_q6", "text": "Feeling bad about yourself or that you are a failure", "domain": "depression"},
    {"id": "phq9_q7", "text": "Trouble concentrating on things", "domain": "depression"},
]

OPTIONS = [
    {"value": 0, "label": "Not at all"},
    {"value": 1, "label": "Several days"},
    {"value": 2, "label": "More than half the days"},
    {"value": 3, "label": "Nearly every day"}
]

def check_api_health():
    """Check if API is running"""
    print("\n" + "="*70)
    print("CHECKING API STATUS")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("✓ API is running!")
            print(f"  Status: {data['status']}")
            print(f"  RAG Loaded: {data['rag_loaded']}")
            print(f"  RAG Documents: {data['total_documents']}")
            return True
        else:
            print(f"✗ API returned status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API")
        print("\n  SOLUTION:")
        print("  1. Open a new terminal")
        print("  2. cd \"D:\\Career\\Grad Project\\UpHeal\\src\\api\"")
        print("  3. python main.py")
        print("  4. Wait for 'Uvicorn running on http://localhost:8000'")
        print("  5. Then run this test script again")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def get_user_answer():
    """Get answer from user (0-3)"""
    print("\nOptions:")
    for opt in OPTIONS:
        print(f"  [{opt['value']}] {opt['label']}")
    
    while True:
        ans = input("Your Answer > ").strip()
        
        # Check if valid number
        if ans in ['0', '1', '2', '3']:
            return int(ans)
        
        # Check if matches label
        ans_lower = ans.lower()
        for opt in OPTIONS:
            if ans_lower in opt['label'].lower():
                return opt['value']
        
        print("Invalid input. Please enter 0, 1, 2, or 3")

def interactive_assessment():
    """Run interactive assessment (simulates real user flow)"""
    print("\n" + "="*70)
    print("INTERACTIVE CLINICAL ASSESSMENT")
    print("="*70)
    print("\nThis simulates how a real user would interact with the website.")
    print("Answer each question honestly (over the last 2 weeks).\n")
    
    input("Press ENTER to begin...")
    
    # Collect answers
    answers = {}
    
    for i, question in enumerate(QUESTIONS, 1):
        print("\n" + "-"*70)
        print(f"[Question {i}/{len(QUESTIONS)}] {question['text']}")
        answer = get_user_answer()
        answers[question['id']] = answer
    
    print("\n" + "="*70)
    print("SENDING TO API...")
    print("="*70)
    
    # Prepare request
    request_data = {
        "answers": answers,
        "user_id": "test_terminal_user",
        "session_id": f"session_{int(time.time())}"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/assess",
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            display_results(response.json())
            
            # Save to file
            with open("my_assessment_result.json", "w", encoding="utf-8") as f:
                json.dump(response.json(), f, indent=2)
            print(f"\n📄 Full results saved to: my_assessment_result.json")
            
        else:
            print(f"\n✗ API returned error {response.status_code}")
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")

def display_results(data):
    """Display assessment results in a nice format"""
    print("\n" + "="*70)
    print("ASSESSMENT RESULTS")
    print("="*70)
    
    # Probabilities
    print("\n📊 CLINICAL ASSESSMENT:")
    print(f"  Anxiety:    {data['anxiety_probability']:.1%} ({data['severity']['anxiety']} severity)")
    print(f"  Depression: {data['depression_probability']:.1%} ({data['severity']['depression']} severity)")
    
    if data['comorbidity']:
        print(f"  ⚠️  Comorbidity detected (both conditions present)")
    
    # RAG Query
    print(f"\n🔍 RAG QUERY GENERATED:")
    print(f"  \"{data['query_used']}\"")
    
    # Recommendations
    print(f"\n📚 TREATMENT RECOMMENDATIONS (from DSM-5-TR):")
    print("  (Based on evidence-based clinical psychology)")
    
    for i, rec in enumerate(data['rag_recommendations'][:5], 1):
        print(f"\n  [{i}] {rec['source']} (Pages: {rec['pages']})")
        print(f"      Section: {rec['section']}")
        print(f"      Relevance: {rec['similarity']}%")
        print(f"      Content: {rec['content'][:200]}...")
    
    print("\n" + "="*70)
    print("This is exactly what the Flutter app will receive!")
    print("="*70)

if __name__ == "__main__":
    import time
    
    print("\n" + "="*70)
    print("UPHEAL API INTERACTIVE TEST")
    print("="*70)
    print("\nThis script simulates a real user taking the assessment on the website.")
    print("It will:")
    print("  1. Ask you questions one by one (like the website)")
    print("  2. Send your answers to the API")
    print("  3. Display the results (what the app will show)")
    
    # Check API first
    if not check_api_health():
        print("\n❌ Cannot proceed without API running. Exiting.")
        sys.exit(1)
    
    # Run interactive assessment
    interactive_assessment()

