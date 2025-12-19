"""
Advanced PDF analysis script to:
1. Re-check language of PDFs
2. Extract PDF metadata and titles
3. Verify file categorization
4. Rename files based on actual titles
"""

import os
from pathlib import Path
import pypdf
from langdetect import detect, LangDetectException
import re


def extract_pdf_metadata(pdf_path):
    """Extract metadata including title from PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            metadata = pdf_reader.metadata
            
            if metadata:
                return {
                    'title': metadata.get('/Title', ''),
                    'author': metadata.get('/Author', ''),
                    'subject': metadata.get('/Subject', ''),
                    'creator': metadata.get('/Creator', '')
                }
    except Exception as e:
        print(f"Error reading metadata from {pdf_path}: {e}")
    
    return None


def extract_more_text(pdf_path, max_pages=10):
    """Extract text from more pages for better language detection"""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            num_pages = min(len(pdf_reader.pages), max_pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                    
                # If we have enough text, stop
                if len(text) > 500:
                    break
    except Exception as e:
        print(f"  Error: {e}")
    
    return text.strip()


def detect_language_robust(text):
    """More robust language detection"""
    if not text or len(text.strip()) < 20:
        return None
    
    # Remove common non-alphabetic characters
    clean_text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    clean_text = ' '.join(clean_text.split())
    
    if len(clean_text) < 20:
        return None
    
    try:
        lang = detect(clean_text)
        return lang
    except LangDetectException:
        return None


def analyze_pdf(pdf_path):
    """Comprehensive PDF analysis"""
    filename = os.path.basename(pdf_path)
    print(f"\nAnalyzing: {filename}")
    
    # Get metadata
    metadata = extract_pdf_metadata(pdf_path)
    title = metadata.get('title', '') if metadata else ''
    
    # Extract more text
    text = extract_more_text(pdf_path, max_pages=10)
    
    # Detect language
    language = detect_language_robust(text)
    
    # Get file size
    file_size = os.path.getsize(pdf_path) / (1024 * 1024)  # MB
    
    # Determine if it's digital or scanned
    text_density = len(text) / file_size if file_size > 0 else 0
    is_digital = text_density > 100  # Characters per MB
    
    result = {
        'filename': filename,
        'path': pdf_path,
        'title': title,
        'language': language,
        'is_digital': is_digital,
        'text_length': len(text),
        'file_size_mb': round(file_size, 2),
        'text_preview': text[:200] if text else ''
    }
    
    print(f"  Title: {title if title else 'N/A'}")
    print(f"  Language: {language if language else 'Unknown'}")
    print(f"  Type: {'Digital' if is_digital else 'Scanned/Image-based'}")
    print(f"  Text extracted: {len(text)} chars")
    print(f"  Text preview: {text[:100]}..." if text else "  No text extracted")
    
    return result


def sanitize_filename(title, max_length=100):
    """Convert title to safe filename"""
    if not title:
        return None
    
    # Remove invalid characters
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
    
    # Replace multiple spaces with single space
    safe_title = ' '.join(safe_title.split())
    
    # Truncate if too long
    if len(safe_title) > max_length:
        safe_title = safe_title[:max_length].rsplit(' ', 1)[0]
    
    return safe_title.strip()


def analyze_all_folders(base_dir):
    """Analyze all PDFs in organized folders"""
    base_path = Path(base_dir)
    
    results = {
        'digital': [],
        'non_english': [],
        'scanned': []
    }
    
    for category in ['digital', 'non_english', 'scanned']:
        folder = base_path / category
        if folder.exists():
            pdf_files = list(folder.glob("*.pdf"))
            print(f"\n{'='*60}")
            print(f"Analyzing {category.upper()} folder: {len(pdf_files)} files")
            print('='*60)
            
            for pdf_file in pdf_files:
                try:
                    result = analyze_pdf(str(pdf_file))
                    results[category].append(result)
                except Exception as e:
                    print(f"  Error analyzing {pdf_file.name}: {e}")
    
    return results


def check_original_vs_organized(original_dir, organized_dir):
    """Verify all files were moved"""
    original_path = Path(original_dir)
    organized_path = Path(organized_dir)
    
    # Get all PDFs from original
    original_pdfs = set([f.name for f in original_path.glob("*.pdf")])
    
    # Get all PDFs from organized folders
    organized_pdfs = set()
    for category in ['digital', 'non_english', 'scanned']:
        folder = organized_path / category
        if folder.exists():
            organized_pdfs.update([f.name for f in folder.glob("*.pdf")])
    
    missing = original_pdfs - organized_pdfs
    extra = organized_pdfs - original_pdfs
    
    print(f"\n{'='*60}")
    print("FILE TRANSFER VERIFICATION")
    print('='*60)
    print(f"Original PDFs: {len(original_pdfs)}")
    print(f"Organized PDFs: {len(organized_pdfs)}")
    print(f"Missing files: {len(missing)}")
    if missing:
        for f in missing:
            print(f"  - {f}")
    
    return {
        'original_count': len(original_pdfs),
        'organized_count': len(organized_pdfs),
        'missing': list(missing),
        'all_transferred': len(missing) == 0
    }


if __name__ == "__main__":
    original_dir = "Downloaded_Books/Books"
    organized_dir = "Downloaded_Books/Books/organized"
    
    # Check file transfer
    transfer_status = check_original_vs_organized(original_dir, organized_dir)
    
    # Analyze all folders
    results = analyze_all_folders(organized_dir)
    
    # Generate report
    print(f"\n\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print('='*60)
    
    for category, files in results.items():
        print(f"\n{category.upper()}: {len(files)} files")
        
        if category == 'non_english':
            print("\n  Re-checking language detection:")
            english_count = sum(1 for f in files if f['language'] == 'en')
            print(f"  - Actually English: {english_count}")
            print(f"  - Other languages: {len(files) - english_count}")
            
            for f in files:
                print(f"\n  {f['filename']}")
                print(f"    Detected language: {f['language']}")
                print(f"    Text preview: {f['text_preview'][:80]}...")
