
import os
import sys
import json
import subprocess
import time

def run_integration():
    print("="*70)
    print("UPHEAL INTEGRATED SYSTEM STARTUP")
    print("="*70)
    
    base_dir = os.getcwd() # Should be 'UpHeal/src/integration'
    # Validating current directory
    if not os.path.exists("../clinical_forms") or not os.path.exists("../rag"):
        print("Error: Please run this script from the 'D:\\Career\\Grad Project\\UpHeal\\src\\integration' folder.")
        return

    # 1. Run Intake Form
    print("\n[1/3] Launching Clinical Intake Form...")
    print("----------------------------------------")
    
    form_dir = os.path.abspath("../clinical_forms")
    os.chdir(form_dir)
    
    try:
        # Run interactive python script
        code = subprocess.call([sys.executable, "interactive_intake.py"])
        
        if code != 0:
            print("\n[Error] Form execution failed or was cancelled.")
            return
            
    except Exception as e:
        print(f"\n[Error] Failed to run form: {e}")
        return

    # 2. Capture Output
    print("\n[2/3] Retrieving Assessment Data...")
    if not os.path.exists("rag_input.json"):
        print("[Error] rag_input.json not found. Did the form complete successfully?")
        return
        
    with open("rag_input.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    query = data.get("query_string")
    if not query:
        print("[Error] No query string found in output.")
        return
        
    print(f"✓ Retrieved Query: \"{query}\"")

    # 3. Query RAG System
    print("\n[3/3] Querying RAG Knowledge Base...")
    print("----------------------------------------")
    
    rag_dir = os.path.abspath("../rag")
    os.chdir(rag_dir)
    
    try:
        # Run query script with argument
        subprocess.call([sys.executable, "query_rag.py", "--query", query])
        
    except Exception as e:
        print(f"\n[Error] RAG query failed: {e}")

if __name__ == "__main__":
    run_integration()
