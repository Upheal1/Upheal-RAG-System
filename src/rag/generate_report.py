"""
Generate comprehensive report with all file details
"""

import os
import sys
from pathlib import Path
import pypdf
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def get_pdf_info(pdf_path):
    """Get PDF info including title, pages, and metadata"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            
            # Get metadata
            metadata = pdf_reader.metadata
            title = metadata.get('/Title', '') if metadata else ''
            author = metadata.get('/Author', '') if metadata else ''
            
            # Get page count
            pages = len(pdf_reader.pages)
            
            # Get file size
            size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
            
            return {
                'title': title if title else 'N/A',
                'author': author if author else 'N/A',
                'pages': pages,
                'size_mb': round(size_mb, 2),
                'filename': os.path.basename(pdf_path)
            }
    except Exception as e:
        return {
            'title': 'Error reading',
            'author': 'N/A',
            'pages': 0,
            'size_mb': 0,
            'filename': os.path.basename(pdf_path),
            'error': str(e)
        }


# Generate report
org_dir = Path("Downloaded_Books/Books/organized")

report = []
report.append("="*80)
report.append("FINAL PDF ORGANIZATION REPORT")
report.append("Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
report.append("="*80)

categories = {
    'english_digital': 'English Digital PDFs (Ready for RAG)',
    'english_scanned': 'English Scanned PDFs (Need Full OCR)',
    'arabic': 'Arabic PDFs',
    'unprocessable': 'Unprocessable PDFs'
}

total_files = 0
total_size = 0

for folder, description in categories.items():
    folder_path = org_dir / folder
    if not folder_path.exists():
        continue
    
    pdf_files = list(folder_path.glob("*.pdf"))
    if not pdf_files:
        continue
    
    report.append(f"\n\n{'='*80}")
    report.append(f"{description.upper()}")
    report.append(f"Location: {folder}/")
    report.append(f"Count: {len(pdf_files)} files")
    report.append("="*80)
    
    folder_size = 0
    files_info = []
    
    for i, pdf_file in enumerate(sorted(pdf_files), 1):
        info = get_pdf_info(str(pdf_file))
        files_info.append(info)
        folder_size += info['size_mb']
        
        report.append(f"\n{i}. {info['filename']}")
        if info['title'] != 'N/A' and info['title'] != info['filename']:
            report.append(f"   Title: {info['title']}")
        report.append(f"   Size: {info['size_mb']} MB | Pages: {info['pages']}")
        if info['author'] != 'N/A':
            report.append(f"   Author: {info['author']}")
    
    report.append(f"\n{'-'*80}")
    report.append(f"Folder Total: {len(pdf_files)} files | {round(folder_size, 2)} MB")
    
    total_files += len(pdf_files)
    total_size += folder_size

# Summary
report.append(f"\n\n{'='*80}")
report.append("OVERALL SUMMARY")
report.append("="*80)
report.append(f"Total PDFs Processed: {total_files}")
report.append(f"Total Size: {round(total_size, 2)} MB")
report.append(f"\nBreakdown:")

for folder, description in categories.items():
    folder_path = org_dir / folder
    if folder_path.exists():
        count = len(list(folder_path.glob("*.pdf")))
        if count > 0:
            report.append(f"  • {description}: {count} files")

report.append(f"\n{'='*80}")
report.append("RECOMMENDATIONS")
report.append("="*80)
report.append("""
1. FOR RAG PIPELINE:
   - Use all 24 files from 'english_digital/' folder
   - These are ready for text extraction and embedding
   - Total: ~132 MB of high-quality English psychology/clinical content

2. OPTIONAL - SCANNED PDFs:
   - 2 files in 'english_scanned/' need full OCR processing
   - Install Poppler to enable pdf2image conversion
   - These contain valuable content but require more processing

3. ARABIC CONTENT:
   - 7 Arabic PDFs saved in 'arabic/' folder
   - Can be used for Arabic RAG if needed in the future

4. UNPROCESSABLE:
   - 3 files couldn't be processed (likely corrupted or special format)
   - Manual review recommended if these are critical
""")

report.append("="*80)
report.append("END OF REPORT")
report.append("="*80)

# Save report
report_text = '\n'.join(report)
output_file = "FINAL_PDF_REPORT.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(report_text)

print(report_text)
print(f"\n\nReport saved to: {output_file}")
