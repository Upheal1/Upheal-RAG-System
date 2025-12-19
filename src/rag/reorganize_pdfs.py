"""
Reorganize PDFs into correct folders and rename them
"""

import os
import sys
from pathlib import Path
import shutil
import pypdf
import re

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def get_pdf_title(pdf_path):
    """Extract title from PDF metadata"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            if pdf_reader.metadata and pdf_reader.metadata.get('/Title'):
                title = pdf_reader.metadata.get('/Title')
                if title and len(title.strip()) > 3:
                    return title.strip()
    except:
        pass
    return None


def sanitize_filename(title):
    """Convert title to safe filename"""
    if not title:
        return None
    
    # Remove invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    # Replace multiple spaces
    safe = ' '.join(safe.split())
    # Remove special characters from start/end
    safe = safe.strip('. -_')
    # Limit length
    if len(safe) > 150:
        safe = safe[:150].rsplit(' ', 1)[0]
    
    return safe if len(safe) > 3 else None


# Setup directories
base_dir = Path("Downloaded_Books/Books")
org_dir = base_dir / "organized"

# Create new structure
(org_dir / "english_digital").mkdir(exist_ok=True)
(org_dir / "english_scanned").mkdir(exist_ok=True)
(org_dir / "arabic").mkdir(exist_ok=True)
(org_dir / "unprocessable").mkdir(exist_ok=True)

print("="*70)
print("REORGANIZING FILES")
print("="*70)

# Files to move from non_english to english folders
english_moves = [
    {
        'file': "759368772-Motivational-Interviewing-Helping-People-Change-and-Grow-4th-Edition-William-R-Miller-Stephen-Rollnick-Z-Library.pdf",
        'title': "Motivational Interviewing",
        'target': 'english_digital'
    },
    {
        'file': "898242574-OceanofPDF-com-Facing-the-Shadow-Patrick-Carnes-2.pdf",
        'title': "Facing the Shadow",
        'target': 'english_scanned'
    },
    {
        'file': "Clinical Handbook of Psychological Disorders, 6th ed A Step-by-Step Treatment Manual-by David H. Barlow.pdf",
        'title': "Clinical Handbook of Psychological Disorders 6th Edition",
        'target': 'english_scanned'
    },
    {
        'file': "Cognitive Behavior Therapy, Second Edition Basics and Beyond.pdf",
        'title': "Cognitive Behavior Therapy - Basics and Beyond 2nd Edition",
        'target': 'english_digital'
    },
    {
        'file': "DSM-5-TR.pdf",
        'title': "DSM-5-TR",
        'target': 'english_digital'
    },
    {
        'file': "The Complete Adult Psychotherapy Treatment Planner (Arthur E. Jongsma, L. Mark Peterson) 5th E.pdf",
        'title': "The Complete Adult Psychotherapy Treatment Planner 5th Edition",
        'target': 'english_digital'
    }
]

# Move and rename English files from non_english
print("\n1. Moving ENGLISH files from 'non_english' folder:")
for item in english_moves:
    src = org_dir / "non_english" / item['file']
    if src.exists():
        target_dir = org_dir / item['target']
        new_name = sanitize_filename(item['title']) + ".pdf"
        dest = target_dir / new_name
        
        shutil.move(str(src), str(dest))
        print(f"   ✓ {item['file'][:50]}...")
        print(f"     -> {item['target']}/{new_name}")

# Move files from old 'digital' folder to 'english_digital'
print("\n2. Moving files from 'digital' to 'english_digital':")
old_digital = org_dir / "digital"
if old_digital.exists():
    for pdf_file in old_digital.glob("*.pdf"):
        # Get title
        title = get_pdf_title(str(pdf_file))
        new_name = sanitize_filename(title) if title else pdf_file.name
        if not new_name.endswith('.pdf'):
            new_name = pdf_file.name
        
        dest = org_dir / "english_digital" / new_name
        
        # Handle duplicates
        counter = 1
        while dest.exists():
            base = new_name[:-4]
            dest = org_dir / "english_digital" / f"{base} ({counter}).pdf"
            counter += 1
        
        shutil.move(str(pdf_file), str(dest))
        print(f"   ✓ {pdf_file.name[:50]}... -> {new_name}")

# Move Arabic files from original folder
print("\n3. Moving ARABIC files:")
arabic_files = [
    "العلاج-السلوكي-المعرفي-ببساطة-CBT.pdf",
    "خطة العلاج النفسي.pdf",
    "علم النفس المرضى.pdf",
    "مرجع_اكلينكي_في_الاضطرابات_النفسية.pdf",
    "معايير+DSM-5-TR.pdf",
    "مهارات المشورة حسب النموذج التطوري لجيرارد ايجان - د اوسم وصفي -[christianlib.com].pdf",
    "نماذج الخطط العلاجية.pdf"
]

for filename in arabic_files:
    src = base_dir / filename
    if src.exists():
        dest = org_dir / "arabic" / filename
        shutil.copy2(str(src), str(dest))
        print(f"   ✓ Copied: {filename}")

# Move remaining files from non_english to unprocessable
print("\n4. Moving unprocessable files:")
remaining = list((org_dir / "non_english").glob("*.pdf"))
for pdf_file in remaining:
    dest = org_dir / "unprocessable" / pdf_file.name
    shutil.move(str(pdf_file), str(dest))
    print(f"   ✓ {pdf_file.name}")

# Clean up old folders
print("\n5. Cleaning up old folders...")
for old_folder in ['digital', 'scanned', 'non_english']:
    folder_path = org_dir / old_folder
    if folder_path.exists() and not list(folder_path.iterdir()):
        folder_path.rmdir()
        print(f"   ✓ Removed empty folder: {old_folder}/")

print("\n" + "="*70)
print("REORGANIZATION COMPLETE!")
print("="*70)

# Count files in each folder
print("\nFinal file distribution:")
for folder in ['english_digital', 'english_scanned', 'arabic', 'unprocessable']:
    folder_path = org_dir / folder
    if folder_path.exists():
        count = len(list(folder_path.glob("*.pdf")))
        print(f"  {folder}/: {count} files")
