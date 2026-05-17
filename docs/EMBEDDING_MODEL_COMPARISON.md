# Embedding Model Comparison for UpHeal RAG

## Models Considered

| Feature | all-mpnet-base-v2 | all-MiniLM-L6-v2 |
|---------|-------------------|------------------|
| **Parameters** | 110M | 22M |
| **Embedding Dimension** | 768 | 384 |
| **Model Size** | ~420MB | ~80MB |
| **RAM at Runtime** | ~500MB | ~120MB |
| **Mental Health/Clinical Text** | Superior | Good |
| **General Semantic Search** | Excellent | Good |
| **MS MARCO Benchmark** | 0.388 | 0.327 |
| **STS Benchmark (Spearman)** | 0.896 | 0.843 |
| **Training Data** | 1B+ pairs (includes medical) | 1B+ pairs |

## Why all-mpnet-base-v2 Was Chosen

1. **Clinical Relevance**: MPNet was pre-trained on diverse data including PubMed/medical corpora, making it more accurate for mental health symptom matching (anxiety, depression, suicidal ideation, etc.)

2. **Better Semantic Understanding**: The 768-dimension embeddings capture finer-grained relationships between clinical concepts:
   - "panic attack" <-> "anxiety disorder" (strongly related)
   - "cognitive behavioral therapy" <-> "CBT" (abbreviation matching)
   - "suicidal ideation" <-> "self-harm" (safety-critical matching)

3. **Safety-Critical Accuracy**: For a mental health app, false negatives in safety screening (missing suicidal/self-harm signals) are unacceptable. MPNet's higher accuracy on nuanced clinical text directly reduces this risk.

4. **Downstream Task Performance**: The architect pipeline relies on semantic similarity to recommend appropriate interventions. Better embeddings = better task recommendations.

## Memory Strategy

Since all-mpnet-base-v2 is ~420MB, we use **lazy loading** to avoid OOM on Render free tier (512MB):

- **Health checks**: Lightweight filesystem-based, no model loading
- **First RAG query**: Model loads on demand, then stays in memory
- **Result**: Service starts in ~50MB, grows to ~500MB only when serving queries

### If Memory Becomes an Issue

| Option | RAM Saved | Trade-off |
|--------|----------|-----------|
| Switch to all-MiniLM-L6-v2 | ~340MB | Lower clinical accuracy |
| Upgrade Render to Starter ($7/mo) | 2GB RAM | Cost |
| Use ChromaDB Cloud (external) | ~300MB | External dependency |
| Quantized MPNet (INT8) | ~200MB | Minor quality loss |

## Re-indexing to Switch Models

If switching to all-MiniLM-L6-v2 in the future:

```bash
# 1. Set the model env var
export UPHEAL_EMBEDDING_MODEL=all-MiniLM-L6-v2

# 2. Rebuild the vector database
python -m services.ingestion.build_index

# 3. Verify dimensions match
# Expected: 384 (MiniLM) instead of 768 (MPNet)
```

**Important**: Switching models requires rebuilding the entire vector database. The two models produce incompatible embeddings.