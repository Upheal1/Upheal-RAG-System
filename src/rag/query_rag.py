"""
Clinical RAG Query System
Retrieves relevant context from the mini vector store (4 books)
"""

import chromadb
from sentence_transformers import SentenceTransformer
import textwrap

print("="*70)
print("CLINICAL RAG RETRIEVAL SYSTEM")
print("="*70)

# Configuration
VECTOR_DB_PATH = "../../data/vector_db_mini"
COLLECTION_NAME = "clinical_rag_mini"
MODEL_NAME = "all-mpnet-base-v2"

# Initialize
print(f"Loading vector store from: {VECTOR_DB_PATH}")
client = chromadb.PersistentClient(path=VECTOR_DB_PATH)

try:
    collection = client.get_collection(name=COLLECTION_NAME)
    print(f"[OK] Connected to collection: {COLLECTION_NAME}")
    print(f"  Total documents: {collection.count()}")
except Exception as e:
    print(f"Error connecting to collection: {e}")
    exit(1)

print(f"Loading embedding model: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME)
print(f"[OK] Model loaded")

def query_rag(question: str, top_k: int = 4):
    """
    Search key: finds semantic matches for the question
    """
    print(f"\n{'-'*70}")
    print(f"Query: {question}")
    print(f"{'-'*70}")
    
    # 1. Embed query
    query_vec = model.encode([question])
    
    # 2. Search vector DB
    results = collection.query(
        query_embeddings=query_vec.tolist(),
        n_results=top_k,
        include=['documents', 'metadatas', 'distances']
    )
    
    # 3. Format results
    context_parts = []
    
    print(f"Found {len(results['documents'][0])} relevant excerpts:\n")
    
    for i, (doc, meta, dist) in enumerate(zip(
        results['documents'][0], 
        results['metadatas'][0], 
        results['distances'][0]
    ), 1):
        similarity = (1 - dist) * 100
        
        # Source info
        source = meta.get('source_file', 'Unknown')
        pages = meta.get('page_numbers', '?')
        header = meta.get('header', 'Section')
        
        print(f"Result #{i} (Similarity: {similarity:.1f}%)")
        print(f"Source: {source} (Pages: {pages})")
        print(f"Section: {header}")
        print(f"Content: \"{textwrap.shorten(doc, width=200, placeholder='...')}\"")
        print()
        
        context_parts.append(f"SOURCE: {source}\nSECTION: {header}\nCONTENT: {doc}")
    
    return "\n\n".join(context_parts)

if __name__ == "__main__":
    print("\nSystem ready! Enter your clinical questions (or 'quit' to exit).")
    
    while True:
        try:
            user_input = input("\nQuestion: ").strip()
            if user_input.lower() in ('quit', 'exit', 'q'):
                break
            
            if not user_input:
                continue
                
            query_rag(user_input)
            
        except KeyboardInterrupt:
            break

    print("\nGoodbye!")
