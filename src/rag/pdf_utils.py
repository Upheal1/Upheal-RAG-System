"""
PDF Processing Utilities for RAG Pipeline
Handles language detection and classification of PDFs
"""

import os
from pathlib import Path
from typing import Tuple, Optional
import pypdf
from langdetect import detect, LangDetectException
import pytesseract
from pdf2image import convert_from_path
from PIL import Image


def extract_text_from_pdf(pdf_path: str, max_pages: int = 3) -> str:
    """
    Extract text from a PDF file using pypdf.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to extract (for speed)
    
    Returns:
        Extracted text as a string
    """
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            num_pages = min(len(pdf_reader.pages), max_pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    
    return text.strip()


def ocr_first_page(pdf_path: str) -> str:
    """
    Perform OCR on the first page of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        OCR extracted text from the first page
    """
    try:
        # Convert first page to image
        images = convert_from_path(pdf_path, first_page=1, last_page=1)
        
        if images:
            # Perform OCR on the first page
            text = pytesseract.image_to_string(images[0])
            return text.strip()
    except Exception as e:
        print(f"Error performing OCR on {pdf_path}: {e}")
    
    return ""


def is_english(text: str, min_length: int = 50) -> bool:
    """
    Check if the given text is in English.
    
    Args:
        text: Text to check
        min_length: Minimum text length required for detection
    
    Returns:
        True if text is English, False otherwise
    """
    if not text or len(text.strip()) < min_length:
        return False
    
    try:
        # langdetect returns 'en' for English
        detected_lang = detect(text)
        return detected_lang == 'en'
    except LangDetectException:
        # If detection fails, assume not English
        return False


def process_pdf(file_path: str) -> Tuple[str, str]:
    """
    Process a PDF file to determine its category.
    
    Flow:
    1. Attempt fast text extraction
    2. If text found -> Detect Language
       - If English -> "digital"
       - Else -> "non_english"
    3. If no text -> OCR First Page
    4. Detect Language on OCR result
       - If English -> "scanned"
       - Else -> "non_english"
    
    Args:
        file_path: Path to the PDF file
    
    Returns:
        Tuple of (category, detected_text)
        category: "digital", "scanned", or "non_english"
    """
    filename = os.path.basename(file_path)
    try:
        print(f"Processing: {filename}")
    except UnicodeEncodeError:
        print(f"Processing: [filename with special characters]")
    
    # Step 1 & 2: Try extracting text directly
    extracted_text = extract_text_from_pdf(file_path)
    
    if extracted_text and len(extracted_text.strip()) > 50:
        # We have text, check language
        if is_english(extracted_text):
            print(f"  -> Digital PDF (English)")
            return "digital", extracted_text
        else:
            print(f"  -> Non-English PDF (Digital)")
            return "non_english", extracted_text
    
    # Step 3 & 4: No text found, try OCR
    print(f"  -> No text found, attempting OCR...")
    ocr_text = ocr_first_page(file_path)
    
    if ocr_text and len(ocr_text.strip()) > 50:
        if is_english(ocr_text):
            print(f"  -> Scanned PDF (English)")
            return "scanned", ocr_text
        else:
            print(f"  -> Non-English PDF (Scanned)")
            return "non_english", ocr_text
    
    # If we can't extract any meaningful text, mark as non-English
    print(f"  -> Could not extract sufficient text, marking as non-English")
    return "non_english", ""


def organize_files(source_dir: str, output_dir: str = None) -> dict:
    """
    Organize PDF files from source directory into categorized folders.
    
    Args:
        source_dir: Directory containing PDF files
        output_dir: Output directory for organized files (default: source_dir/organized)
    
    Returns:
        Dictionary with statistics about processed files
    """
    source_path = Path(source_dir)
    
    if output_dir is None:
        output_path = source_path / "organized"
    else:
        output_path = Path(output_dir)
    
    # Create output directories
    digital_dir = output_path / "digital"
    scanned_dir = output_path / "scanned"
    non_english_dir = output_path / "non_english"
    
    digital_dir.mkdir(parents=True, exist_ok=True)
    scanned_dir.mkdir(parents=True, exist_ok=True)
    non_english_dir.mkdir(parents=True, exist_ok=True)
    
    # Statistics
    stats = {
        "digital": 0,
        "scanned": 0,
        "non_english": 0,
        "errors": 0
    }
    
    # Process all PDF files
    pdf_files = list(source_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {source_dir}")
        return stats
    
    print(f"\nFound {len(pdf_files)} PDF files to process\n")
    
    for pdf_file in pdf_files:
        try:
            category, _ = process_pdf(str(pdf_file))
            
            # Determine destination
            if category == "digital":
                dest_dir = digital_dir
            elif category == "scanned":
                dest_dir = scanned_dir
            else:
                dest_dir = non_english_dir
            
            # Copy file to destination
            dest_file = dest_dir / pdf_file.name
            
            # If file already exists, add a number
            counter = 1
            while dest_file.exists():
                dest_file = dest_dir / f"{pdf_file.stem}_{counter}{pdf_file.suffix}"
                counter += 1
            
            # Copy the file
            import shutil
            shutil.copy2(pdf_file, dest_file)
            
            stats[category] += 1
            
        except Exception as e:
            try:
                print(f"Error processing {pdf_file.name}: {e}")
            except UnicodeEncodeError:
                print(f"Error processing file with special characters: {e}")
            stats["errors"] += 1
    
    # Print summary
    print("\n" + "="*50)
    print("PROCESSING SUMMARY")
    print("="*50)
    print(f"Digital PDFs (English):     {stats['digital']}")
    print(f"Scanned PDFs (English):     {stats['scanned']}")
    print(f"Non-English PDFs:           {stats['non_english']}")
    print(f"Errors:                     {stats['errors']}")
    print(f"Total:                      {len(pdf_files)}")
    print("="*50)
    
    return stats


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        source_directory = sys.argv[1]
    else:
        source_directory = input("Enter the path to the directory containing PDFs: ")
    
    if os.path.exists(source_directory):
        organize_files(source_directory)
    else:
        print(f"Directory not found: {source_directory}")
