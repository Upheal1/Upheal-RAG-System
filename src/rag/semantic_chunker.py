"""
Semantic Chunking System for RAG
Chunks PDFs by headers and document structure, not fixed size
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple
import pypdf
from dataclasses import dataclass
import json

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


@dataclass
class Chunk:
    """Represents a semantic chunk of text"""
    text: str
    metadata: Dict
    chunk_id: str
    source_file: str
    page_numbers: List[int]
    header_hierarchy: List[str]
    char_count: int
    
    def to_dict(self):
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'source_file': self.source_file,
            'page_numbers': self.page_numbers,
            'header_hierarchy': self.header_hierarchy,
            'char_count': self.char_count,
            'metadata': self.metadata
        }


class SemanticChunker:
    """
    Chunks PDF documents by semantic structure (headers) rather than fixed size
    """
    
    def __init__(self, min_chunk_size=200, max_chunk_size=2000, overlap=100):
        """
        Args:
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk (for very long sections)
            overlap: Character overlap between chunks when splitting long sections
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        
        # Common header patterns in academic/clinical texts
        self.header_patterns = [
            # Chapter numbers
            r'^(?:Chapter|CHAPTER)\s+\d+[:\.\s]+(.+)$',
            r'^(?:Ch\.|CH\.)\s*\d+[:\.\s]+(.+)$',
            
            # Numbered sections
            r'^(\d+\.(?:\d+\.)*)\s+(.+)$',  # 1.1, 1.1.1, etc.
            
            # All caps headers (common in PDFs)
            r'^([A-Z][A-Z\s]{3,})$',
            
            # Title case headers
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,})$',
            
            # Bullet points or list items at start
            r'^[•\-\*]\s+(.+)$',
        ]
    
    def extract_text_with_structure(self, pdf_path: str) -> List[Dict]:
        """
        Extract text from PDF with page numbers and potential header detection
        
        Returns:
            List of dicts with 'page', 'text', 'is_likely_header' keys
        """
        pages_data = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text()
                    
                    if text:
                        pages_data.append({
                            'page': page_num,
                            'text': text,
                            'lines': text.split('\n')
                        })
        except Exception as e:
            print(f"Error extracting from {pdf_path}: {e}")
            return []
        
        return pages_data
    
    def detect_headers(self, lines: List[str]) -> List[Tuple[int, str, int]]:
        """
        Detect headers in lines of text
        
        Returns:
            List of (line_index, header_text, header_level) tuples
        """
        headers = []
        
        for idx, line in enumerate(lines):
            line = line.strip()
            
            if not line or len(line) < 3:
                continue
            
            # Check for all caps (likely header)
            if len(line) < 100 and line.isupper() and ' ' in line:
                headers.append((idx, line, 1))
                continue
            
            # Check numbered sections (1.1, 2.3.4, etc.)
            numbered_match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)$', line)
            if numbered_match:
                section_num = numbered_match.group(1)
                header_text = numbered_match.group(2)
                level = section_num.count('.') + 1
                headers.append((idx, f"{section_num} {header_text}", level))
                continue
            
            # Check for "Chapter" or similar
            chapter_match = re.match(r'^(?:Chapter|CHAPTER|Section|SECTION)\s+(\d+)[:\.\s]*(.*)$', line)
            if chapter_match:
                headers.append((idx, line, 0))  # Level 0 for chapters
                continue
            
            # Short lines in title case at line start (potential headers)
            if (len(line) < 100 and 
                line[0].isupper() and 
                not line.endswith('.') and
                not line.endswith(',') and
                sum(1 for c in line if c.isupper()) >= 2):
                headers.append((idx, line, 2))
        
        return headers
    
    def chunk_by_headers(self, pdf_path: str, source_filename: str) -> List[Chunk]:
        """
        Create semantic chunks based on document headers
        
        Args:
            pdf_path: Path to PDF file
            source_filename: Name to use in metadata
            
        Returns:
            List of Chunk objects
        """
        print(f"Processing: {source_filename}")
        
        # Extract text with structure
        pages_data = self.extract_text_with_structure(pdf_path)
        
        if not pages_data:
            print(f"  ⚠️ No text extracted")
            return []
        
        # Combine all text and track page boundaries
        all_lines = []
        line_to_page = {}
        current_line_idx = 0
        
        for page_data in pages_data:
            for line in page_data['lines']:
                all_lines.append(line)
                line_to_page[current_line_idx] = page_data['page']
                current_line_idx += 1
        
        # Detect headers
        headers = self.detect_headers(all_lines)
        
        print(f"  Found {len(headers)} potential headers")
        
        if len(headers) < 3:
            # Not enough structure - use paragraph-based chunking
            print(f"  Using paragraph-based chunking (insufficient headers)")
            return self.chunk_by_paragraphs(all_lines, line_to_page, source_filename)
        
        # Create chunks between headers
        chunks = []
        
        for i, (header_idx, header_text, header_level) in enumerate(headers):
            # Determine chunk boundaries
            start_idx = header_idx
            
            if i < len(headers) - 1:
                end_idx = headers[i + 1][0]
            else:
                end_idx = len(all_lines)
            
            # Extract chunk text
            chunk_lines = all_lines[start_idx:end_idx]
            chunk_text = '\n'.join(chunk_lines).strip()
            
            # Skip very small chunks
            if len(chunk_text) < self.min_chunk_size:
                continue
            
            # Get page numbers for this chunk
            chunk_pages = sorted(set(
                line_to_page.get(idx, 1) 
                for idx in range(start_idx, end_idx) 
                if idx in line_to_page
            ))
            
            # If chunk is too large, split it intelligently
            if len(chunk_text) > self.max_chunk_size:
                sub_chunks = self._split_large_chunk(
                    chunk_text, 
                    chunk_pages, 
                    header_text,
                    source_filename,
                    len(chunks)
                )
                chunks.extend(sub_chunks)
            else:
                # Create chunk
                chunk = Chunk(
                    text=chunk_text,
                    metadata={
                        'header': header_text,
                        'header_level': header_level
                    },
                    chunk_id=f"{source_filename}_chunk_{len(chunks)}",
                    source_file=source_filename,
                    page_numbers=chunk_pages,
                    header_hierarchy=[header_text],
                    char_count=len(chunk_text)
                )
                chunks.append(chunk)
        
        print(f"  ✓ Created {len(chunks)} semantic chunks")
        return chunks
    
    def _split_large_chunk(self, text: str, pages: List[int], header: str, 
                          source: str, base_idx: int) -> List[Chunk]:
        """Split a large chunk at paragraph boundaries with overlap"""
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        current_pages = []
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < self.max_chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunk = Chunk(
                        text=current_chunk.strip(),
                        metadata={'header': header, 'split_part': len(chunks) + 1},
                        chunk_id=f"{source}_chunk_{base_idx + len(chunks)}",
                        source_file=source,
                        page_numbers=pages,
                        header_hierarchy=[header],
                        char_count=len(current_chunk)
                    )
                    chunks.append(chunk)
                
                # Start new chunk with overlap
                current_chunk = para + "\n\n"
        
        # Add final chunk
        if current_chunk.strip():
            chunk = Chunk(
                text=current_chunk.strip(),
                metadata={'header': header, 'split_part': len(chunks) + 1},
                chunk_id=f"{source}_chunk_{base_idx + len(chunks)}",
                source_file=source,
                page_numbers=pages,
                header_hierarchy=[header],
                char_count=len(current_chunk)
            )
            chunks.append(chunk)
        
        return chunks
    
    def chunk_by_paragraphs(self, lines: List[str], line_to_page: Dict, 
                           source_filename: str) -> List[Chunk]:
        """Fallback: chunk by paragraphs when no clear headers exist"""
        
        text = '\n'.join(lines)
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = ""
        current_pages = set()
        
        for i, para in enumerate(paragraphs):
            if len(current_chunk) + len(para) < self.max_chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip():
                    chunk = Chunk(
                        text=current_chunk.strip(),
                        metadata={'type': 'paragraph_based'},
                        chunk_id=f"{source_filename}_chunk_{len(chunks)}",
                        source_file=source_filename,
                        page_numbers=sorted(current_pages) if current_pages else [1],
                        header_hierarchy=["Document"],
                        char_count=len(current_chunk)
                    )
                    chunks.append(chunk)
                
                current_chunk = para + "\n\n"
                current_pages.clear()
        
        # Final chunk
        if current_chunk.strip():
            chunk = Chunk(
                text=current_chunk.strip(),
                metadata={'type': 'paragraph_based'},
                chunk_id=f"{source_filename}_chunk_{len(chunks)}",
                source_file=source_filename,
                page_numbers=[1],
                header_hierarchy=["Document"],
                char_count=len(current_chunk)
            )
            chunks.append(chunk)
        
        return chunks


def process_all_pdfs(pdf_directory: str, output_dir: str):
    """Process all PDFs in directory and save chunks"""
    
    pdf_dir = Path(pdf_directory)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    chunker = SemanticChunker(
        min_chunk_size=200,
        max_chunk_size=2000,
        overlap=100
    )
    
    all_chunks = []
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    print(f"\n{'='*70}")
    print(f"SEMANTIC CHUNKING - Processing {len(pdf_files)} PDFs")
    print('='*70)
    
    for pdf_file in pdf_files:
        chunks = chunker.chunk_by_headers(
            str(pdf_file),
            pdf_file.stem  # filename without extension
        )
        all_chunks.extend(chunks)
        print()
    
    # Save chunks as JSON
    chunks_data = [chunk.to_dict() for chunk in all_chunks]
    
    output_file = output_path / "semantic_chunks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, indent=2, ensure_ascii=False)
    
    # Save summary
    summary_file = output_path / "chunking_summary.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"Semantic Chunking Summary\n")
        f.write(f"{'='*70}\n\n")
        f.write(f"Total PDFs processed: {len(pdf_files)}\n")
        f.write(f"Total chunks created: {len(all_chunks)}\n")
        f.write(f"Average chunk size: {sum(c.char_count for c in all_chunks) // len(all_chunks)} chars\n")
        f.write(f"\nChunks by source:\n")
        
        from collections import Counter
        source_counts = Counter(c.source_file for c in all_chunks)
        for source, count in sorted(source_counts.items()):
            f.write(f"  {source}: {count} chunks\n")
    
    print(f"\n{'='*70}")
    print(f"COMPLETED")
    print('='*70)
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Saved to: {output_file}")
    print(f"Summary: {summary_file}")
    
    return all_chunks


if __name__ == "__main__":
    # Process English digital PDFs
    pdf_directory = "Downloaded_Books/Books/organized/english_digital"
    output_directory = "rag_data"
    
    if Path(pdf_directory).exists():
        chunks = process_all_pdfs(pdf_directory, output_directory)
    else:
        print(f"Error: Directory not found: {pdf_directory}")
