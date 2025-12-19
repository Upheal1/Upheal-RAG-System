import json

# Load chunks
with open('rag_data/semantic_chunks.json', 'r', encoding='utf-8') as f:
    chunks = json.load(f)

print("="*70)
print("SEMANTIC CHUNKS - Sample Preview")
print("="*70)
print(f"\nTotal chunks: {len(chunks):,}")
print(f"Data file size: 32.9 MB")
print(f"\n{'-'*70}")
print("Sample Chunks:")
print('-'*70)

# Show first 5 chunks
for i, chunk in enumerate(chunks[:5], 1):
    print(f"\n{i}. Chunk ID: {chunk['chunk_id']}")
    print(f"   Source: {chunk['source_file']}")
    print(f"   Header: {chunk['header_hierarchy'][0] if chunk['header_hierarchy'] else 'N/A'}")
    print(f"   Pages: {chunk['page_numbers']}")
    print(f"   Size: {chunk['char_count']} characters")
    print(f"   Text preview:")
    print(f"   {chunk['text'][:200].strip()}...")
    print()

print(f"{'-'*70}")
print("\nChunk Size Statistics:")
sizes = [c['char_count'] for c in chunks]
print(f"  Minimum: {min(sizes)} chars")
print(f"  Maximum: {max(sizes)} chars")
print(f"  Average: {sum(sizes) // len(sizes)} chars")
print(f"  Total text: {sum(sizes):,} characters")
