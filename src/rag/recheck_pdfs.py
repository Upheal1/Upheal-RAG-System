"""
Re-check and reorganize PDFs properly
"""

import os
import sys
from pathlib import Path
import pypdf
from langdetect import detect, LangDetectException
import shutil
import re

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def extract_text_carefully(pdf_path, max_pages=10):
    """Extract text from multiple pages"""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            num_pages = min(len(pdf_reader.pages), max_pages)
            
            for page_num in range(num_pages):
                try:
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                        if len(text) > 500:
                            break
                except:
                    continue
    except Exception as e:
        pass
    
    return text.strip()


def is_arabic_text(text):
    """Check if text contains Arabic characters"""
    if not text:
        return False
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+')
    return bool(arabic_pattern.search(text))


def detect_language_careful(text):
    """Careful language detection"""
    if not text or len(text.strip()) < 30:
        return None
    
    # Check for Arabic first
    if is_arabic_text(text):
        return 'ar'
    
    # Clean text for language detection
    clean_text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    clean_text = ' '.join(clean_text.split())
    
    if len(clean_text) < 30:
        return None
    
    try:
        lang = detect(clean_text)
        return lang
    except:
        return None


def get_pdf_title(pdf_path):
    """Extract title from PDF metadata"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            if pdf_reader.metadata and pdf_reader.metadata.get('/Title'):
                title = pdf_reader.metadata.get('/Title')
                if title and len(title.strip()) > 0:
                    return title.strip()
    except:
        pass
    return None


def recheck_pdf(pdf_path):
    """Re-check a PDF with better methods"""
    filename = os.path.basename(pdf_path)
    
    # Extract text
    text = extract_text_carefully(pdf_path, max_pages=10)
    
    # Get title
    title = get_pdf_title(pdf_path)
    
    # Detect language
    lang = detect_language_careful(text)
    
    # Determine type
    file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    text_density = len(text) / file_size_mb if file_size_mb > 0 else 0
    is_digital = text_density > 100
    
    return {
        'filename': filename,
        'title': title,
        'language': lang,
        'is_digital': is_digital,
        'text_length': len(text),
        'text_preview': text[:150]
    }


# Re-check non_english folder
print("="*70)
print("RE-CHECKING 'non_english' FOLDER")
print("="*70)

non_english_dir = Path("Downloaded_Books/Books/organized/non_english")
results = []

for pdf_file in non_english_dir.glob("*.pdf"):
    print(f"\nFile: {pdf_file.name}")
    result = recheck_pdf(str(pdf_file))
    result['path'] = str(pdf_file)
    results.append(result)
    
    print(f"  Title: {result['title'] or 'N/A'}")
    print(f"  Language: {result['language'] or 'Unknown'}")
    print(f"  Type: {'Digital' if result['is_digital'] else 'Scanned'}")
    print(f"  Text: {result['text_length']} chars")
    if result['text_preview']:
        print(f"  Preview: {result['text_preview'][:100]}...")

# Count English files
english_files = [r for r in results if r['language'] == 'en']
arabic_files = [r for r in results if r['language'] == 'ar']
unknown_files = [r for r in results if r['language'] not in ['en', 'ar']]

print("\n" + "="*70)
print("SUMMARY OF 'non_english' FOLDER")
print("="*70)
print(f"Total files: {len(results)}")
print(f"Actually English: {len(english_files)}")
print(f"Arabic: {len(arabic_files)}")
print(f"Unknown/Other: {len(unknown_files)}")

# Now check Arabic files in original folder
print("\n" + "="*70)
print("CHECKING ARABIC FILES IN ORIGINAL FOLDER")
print("="*70)

original_dir = Path("Downloaded_Books/Books")
arabic_filenames = [
    "العلاج-السلوكي-المعرفي-ببساطة-CBT.pdf",
    "خطة العلاج النفسي.pdf",
    "علم النفس المرضى.pdf",
    "مرجع_اكلينكي_في_الاضطرابات_النفسية.pdf",
    "معايير+DSM-5-TR.pdf",
    "مهارات المشورة حسب النموذج التطوري لجيرارد ايجان - د اوسم وصفي -[christianlib.com].pdf",
    "نماذج الخطط العلاجية.pdf"
]

arabic_results = []
for filename in arabic_filenames:
    pdf_path = original_dir / filename
    if pdf_path.exists():
        print(f"\nFile: {filename}")
        result = recheck_pdf(str(pdf_path))
        result['path'] = str(pdf_path)
        arabic_results.append(result)
        print(f"  Language: {result['language']}")
        print(f"  Text: {result['text_length']} chars")

print("\n" + "="*70)
print("REORGANIZATION PLAN")
print("="*70)
print(f"\n1. Move {len(english_files)} ENGLISH files from 'non_english' to:")
for f in english_files:
    target = 'digital' if f['is_digital'] else 'scanned'
    print(f"   - {f['filename'][:60]}... -> {target}/")

print(f"\n2. Create 'arabic' folder and move {len(arabic_results)} Arabic PDFs")

print(f"\n3. Keep {len(arabic_files) + len(unknown_files)} files in 'non_english' (if any are truly non-English)")
