
import os
import json
import shutil
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from tqdm import tqdm
from semantic_chunker import SemanticChunker

# Configuration
PDF_PATH = r"D:\Career\Grad Project\RAG\Downloaded_Books\Books\DSM-5-TR.pdf" 
VECTOR_DB_PATH = "vector_db" # Rebuilding the main one, or should I overwrite mini? User said "delete all previous... embed only DSM-5-TR"
# I will use 'vector_db' as the main target and 'vector_db_mini' just incase user code refers to it.
# Actually, the integrated system uses `vector_db_mini`. I should check which one `query_rag.py` uses.
# query_rag.py line 15: VECTOR_DB_PATH = "vector_db_mini"
# integrated_clinical_system.py# Configuration
CHUNKS_FILE = "../../data/rag_chunks/semantic_chunks.json"
VECTOR_DB_PATH = "../../data/vector_db_mini"
COLLECTION_NAME = "clinical_rag_mini"
MODEL_NAME = "all-mpnet-base-v2"
BATCH_SIZE = 50

def process_dsm5():
    print("="*70)
    print("PROCESSING DSM-5-TR (FROM EXISTING CHUNKS)")
    print("="*70)

    # 1. Load and Filter Chunks
    print(f"\n1. Loading chunks from: {CHUNKS_FILE}")
    if not os.path.exists(CHUNKS_FILE):
        print(f"Error: File not found at {CHUNKS_FILE}")
        return

    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        all_chunks = json.load(f)

    print(f"   Total chunks available: {len(all_chunks)}")
    
    # Filter for DSM-5-TR
    dsm_chunks = [c for c in all_chunks if "DSM-5-TR" in c.get('source_file', '')]
    
    if not dsm_chunks:
        print("   Warning: No chunks found with source 'DSM-5-TR'")
        return
        
    print(f"   Filtered {len(dsm_chunks)} DSM-5-TR chunks.")

    # 2. Reset Vector DB
    print(f"\n2. Resetting Vector DB at: {VECTOR_DB_PATH}")
    # (Directory cleanup is optional if using delete_collection, but good for a fresh start if corrupted)
    if os.path.exists(VECTOR_DB_PATH):
        try:
            shutil.rmtree(VECTOR_DB_PATH)
            print("   Deleted existing vector_db_mini directory.")
        except Exception as e:
            print(f"   Warning: Could not delete directory: {e}")

    # 3. Embed and Store
    print(f"\n3. Embedding and Storing...")
    model = SentenceTransformer(MODEL_NAME)
    
    Path(VECTOR_DB_PATH).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"   Deleted existing collection: {COLLECTION_NAME}")
    except ValueError:
        pass # Collection didn't exist

    collection = client.create_collection(name=COLLECTION_NAME)

    total_chunks = len(dsm_chunks)
    num_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in tqdm(range(num_batches), desc="Embedding Batches"):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_chunks)
        batch = dsm_chunks[start_idx:end_idx]
        
        docs = [c['text'] for c in batch]
        ids = [c['chunk_id'] for c in batch]
        metadatas = [{
            'source_file': c['source_file'],
            'page_numbers': str(c['page_numbers']),
            'header': c['header_hierarchy'][0] if c['header_hierarchy'] else '',
        } for c in batch]
        
        embeddings = model.encode(docs, show_progress_bar=False)
        
        collection.add(
            embeddings=embeddings.tolist(),
            documents=docs,
            ids=ids,
            metadatas=metadatas
        )
    
    print("\nSUCCESS: DSM-5-TR has been embedded into vector_db_mini.")

if __name__ == "__main__":
    process_dsm5()
