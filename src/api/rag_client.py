"""
RAG Client - Wrapper around the RAG query system
"""
import sys
import os
from pathlib import Path

# Add parent directories to path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir.parent / 'rag'))

from sentence_transformers import SentenceTransformer
import chromadb

class RAGClient:
    """Client for querying the RAG vector database"""
    
    def __init__(self):
        """Initialize RAG client with ChromaDB and embedding model"""
        # Path relative to api/ folder
        self.vector_db_path = str(current_dir.parent.parent / 'data' / 'vector_db_mini')
        self.collection_name = "clinical_rag_mini"
        self.model_name = "all-mpnet-base-v2"
        
        print(f"Loading RAG from: {self.vector_db_path}")
        
        # Load model and database
        self.model = SentenceTransformer(self.model_name)
        self.client = chromadb.PersistentClient(path=self.vector_db_path)
        self.collection = self.client.get_collection(name=self.collection_name)
        
        print(f"✓ RAG loaded: {self.collection.count()} documents")
        
    def is_loaded(self) -> bool:
        """Check if RAG system is properly loaded"""
        try:
            return self.collection.count() > 0
        except:
            return False
    
    def get_document_count(self) -> int:
        """Get total number of documents in vector DB"""
        return self.collection.count()
        
    def query(self, query_string: str, top_k: int = 5) -> list:
        """
        Query the RAG system
        
        Args:
            query_string: Natural language query
            top_k: Number of results to return
            
        Returns:
            List of recommendations with source, section, content, similarity
        """
        # Generate embedding
        query_embedding = self.model.encode([query_string])
        
        # Search vector database
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        recommendations = []
        for doc, meta, dist in zip(
            results['documents'][0], 
            results['metadatas'][0], 
            results['distances'][0]
        ):
            recommendations.append({
                "source": meta.get('source_file', 'Unknown'),
                "section": meta.get('header', 'Section'),
                "content": doc,
                "similarity": round((1 - dist) * 100, 1),
                "pages": meta.get('page_numbers', '?')
            })
        
        return recommendations
