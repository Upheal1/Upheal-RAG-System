"""
Build Vector Store with Embeddings
Generates embeddings using all-mpnet-base-v2 and stores in ChromaDB
"""

import json
import os
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from tqdm import tqdm

print("="*70)
print("BUILDING VECTOR STORE FOR RAG")
print("="*70)

# Configuration
CHUNKS_FILE = "rag_data/semantic_chunks.json"
VECTOR_DB_PATH = "vector_db"
COLLECTION_NAME = "clinical_psychology_rag"
MODEL_NAME = "all-mpnet-base-v2"
BATCH_SIZE = 100

print(f"\nConfiguration:")
print(f"  Model: {MODEL_NAME}")
print(f"  Vector DB: {VECTOR_DB_PATH}")
print(f"  Collection: {COLLECTION_NAME}")
print(f"  Batch Size: {BATCH_SIZE}")

# Load chunks
print(f"\nLoading chunks from {CHUNKS_FILE}...")
with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
    chunks_data = json.load(f)

print(f"Loaded {len(chunks_data):,} chunks")

# Initialize embedding model
print(f"\nInitializing embedding model: {MODEL_NAME}")
print("(This will download the model on first run)")
model = SentenceTransformer(MODEL_NAME)
print(f"✓ Model loaded successfully")
print(f"  Embedding dimension: {model.get_sentence_embedding_dimension()}")

# Initialize ChromaDB
print(f"\nInitializing ChromaDB...")
Path(VECTOR_DB_PATH).mkdir(parents=True, exist_ok=True)

client = chromadb.PersistentClient(path=VECTOR_DB_PATH)

# Delete existing collection if it exists
try:
    client.delete_collection(name=COLLECTION_NAME)
    print(f"  Deleted existing collection: {COLLECTION_NAME}")
except:
    pass

# Create new collection
collection = client.create_collection(
    name=COLLECTION_NAME,
    metadata={"description": "Clinical Psychology RAG - Semantic chunks from 24 textbooks"}
)
print(f"✓ Collection created: {COLLECTION_NAME}")

# Process chunks in batches
print(f"\nGenerating embeddings and adding to vector store...")
print(f"Processing in batches of {BATCH_SIZE}...")

total_chunks = len(chunks_data)
num_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE

for batch_idx in tqdm(range(num_batches), desc="Batches"):
    start_idx = batch_idx * BATCH_SIZE
    end_idx = min(start_idx + BATCH_SIZE, total_chunks)
    
    batch_chunks = chunks_data[start_idx:end_idx]
    
    # Prepare batch data
    documents = [chunk['text'] for chunk in batch_chunks]
    ids = [chunk['chunk_id'] for chunk in batch_chunks]
    
    # Prepare metadata (ChromaDB requires flat metadata)
    metadatas = []
    for chunk in batch_chunks:
        meta = {
            'source_file': chunk['source_file'],
            'char_count': chunk['char_count'],
            'page_numbers': str(chunk['page_numbers']),  # Convert list to string
            'header': chunk['header_hierarchy'][0] if chunk['header_hierarchy'] else '',
        }
        metadatas.append(meta)
    
    # Generate embeddings for this batch
    embeddings = model.encode(documents, show_progress_bar=False)
    
    # Add to collection
    collection.add(
        embeddings=embeddings.tolist(),
        documents=documents,
        ids=ids,
        metadatas=metadatas
    )

print("\n" + "="*70)
print("VECTOR STORE BUILD COMPLETE!")
print("="*70)

# Get collection info
print(f"\nCollection Statistics:")
print(f"  Total documents: {collection.count():,}")
print(f"  Storage location: {VECTOR_DB_PATH}")

# Test query
print(f"\n" + "="*70)
print("TESTING RETRIEVAL")
print("="*70)

test_queries = [
    "What are the symptoms of major depressive disorder?",
    "How to treat anxiety disorders with CBT?",
    "Motivational interviewing techniques for addiction"
]

for query in test_queries:
    print(f"\nQuery: '{query}'")
    
    # Generate query embedding
    query_embedding = model.encode([query])[0]
    
    # Search
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=3
    )
    
    print(f"  Top 3 results:")
    for i, (doc, meta, distance) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    ), 1):
        print(f"\n  {i}. Source: {meta['source_file']}")
        print(f"     Header: {meta['header']}")
        print(f"     Pages: {meta['page_numbers']}")
        print(f"     Similarity: {1 - distance:.4f}")
        print(f"     Preview: {doc[:150]}...")

print(f"\n" + "="*70)
print("SUCCESS! Vector store is ready for RAG queries")
print("="*70)

# Save configuration
config = {
    "model_name": MODEL_NAME,
    "embedding_dimension": model.get_sentence_embedding_dimension(),
    "total_chunks": total_chunks,
    "collection_name": COLLECTION_NAME,
    "vector_db_path": VECTOR_DB_PATH
}

with open(f"{VECTOR_DB_PATH}/config.json", 'w') as f:
    json.dump(config, f, indent=2)

print(f"\nConfiguration saved to: {VECTOR_DB_PATH}/config.json")
