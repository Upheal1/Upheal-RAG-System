"""
Test script for PDF processing utilities
Creates sample PDFs and tests the classification system
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def create_test_pdfs(test_dir="test_pdfs"):
    """
    Create sample PDFs for testing:
    1. A digital English PDF
    2. A digital non-English PDF (French)
    3. A scanned-like English PDF (image-based)
    """
    test_path = Path(test_dir)
    test_path.mkdir(exist_ok=True)
    
    print("Creating test PDFs...")
    
    # 1. Digital English PDF
    print("  Creating digital_english.pdf...")
    c = canvas.Canvas(str(test_path / "digital_english.pdf"), pagesize=letter)
    c.setFont("Helvetica", 12)
    
    text = """
    This is a sample English document for testing the PDF processing pipeline.
    It contains regular text that can be extracted directly without OCR.
    This document should be classified as a 'digital' English PDF.
    
    The quick brown fox jumps over the lazy dog.
    Machine learning and artificial intelligence are transforming how we process documents.
    Natural language processing enables us to understand and analyze text at scale.
    """
    
    y = 750
    for line in text.strip().split('\n'):
        c.drawString(50, y, line.strip())
        y -= 20
    
    c.save()
    
    # 2. Digital French PDF
    print("  Creating digital_french.pdf...")
    c = canvas.Canvas(str(test_path / "digital_french.pdf"), pagesize=letter)
    c.setFont("Helvetica", 12)
    
    text_fr = """
    Ceci est un document français pour tester le pipeline de traitement PDF.
    Il contient du texte régulier qui peut être extrait directement sans OCR.
    Ce document devrait être classé comme un PDF français.
    
    Le renard brun rapide saute par-dessus le chien paresseux.
    L'apprentissage automatique et l'intelligence artificielle transforment notre façon de traiter les documents.
    Le traitement du langage naturel nous permet de comprendre et d'analyser le texte à grande échelle.
    """
    
    y = 750
    for line in text_fr.strip().split('\n'):
        c.drawString(50, y, line.strip())
        y -= 20
    
    c.save()
    
    # 3. Image-based PDF (simulating scanned document)
    print("  Creating scanned_english.pdf...")
    
    # Create an image with text
    img = Image.new('RGB', (612, 792), color='white')
    draw = ImageDraw.Draw(img)
    
    # Use default font
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    text_img = """This is a scanned English document.
It is stored as an image within the PDF.
OCR will be needed to extract this text.
This should be classified as 'scanned' English PDF.

Machine learning helps us process scanned documents.
Optical Character Recognition converts images to text."""
    
    y_pos = 100
    for line in text_img.strip().split('\n'):
        draw.text((50, y_pos), line, fill='black', font=font)
        y_pos += 40
    
    # Save image temporarily
    temp_img_path = test_path / "temp_image.png"
    img.save(temp_img_path)
    
    # Create PDF from image
    c = canvas.Canvas(str(test_path / "scanned_english.pdf"), pagesize=letter)
    c.drawImage(str(temp_img_path), 0, 0, width=612, height=792)
    c.save()
    
    # Clean up temp image
    temp_img_path.unlink()
    
    print(f"\nTest PDFs created in '{test_dir}/' directory")
    print("  - digital_english.pdf")
    print("  - digital_french.pdf")
    print("  - scanned_english.pdf")
    
    return test_path


def run_test():
    """Run the test by creating PDFs and processing them"""
    print("="*60)
    print("PDF PROCESSING TEST")
    print("="*60)
    
    # Create test PDFs
    test_dir = create_test_pdfs()
    
    print("\n" + "="*60)
    print("PROCESSING TEST PDFs")
    print("="*60 + "\n")
    
    # Import and run the processor
    from pdf_utils import organize_files
    
    stats = organize_files(str(test_dir))
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print(f"\nCheck the '{test_dir}/organized/' directory for results:")
    print("  - digital/     should contain: digital_english.pdf")
    print("  - scanned/     should contain: scanned_english.pdf")
    print("  - non_english/ should contain: digital_french.pdf")


if __name__ == "__main__":
    # Check if reportlab is installed
    try:
        import reportlab
        run_test()
    except ImportError:
        print("Error: reportlab is required for creating test PDFs")
        print("Install it with: pip install reportlab")
        print("\nAlternatively, you can skip the test and use the utilities directly on your own PDFs.")
