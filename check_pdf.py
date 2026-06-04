# check_pdf.py
import pdfplumber

pdf_path = "data/patient2.pdf"

print(f"Checking PDF: {pdf_path}")
print("="*50)

with pdfplumber.open(pdf_path) as pdf:
    print(f"Number of pages: {len(pdf.pages)}")
    print()
    
    for i, page in enumerate(pdf.pages[:5]):  # First 5 pages only
        text = page.extract_text()
        print(f"Page {i+1}:")
        print(f"  Text length: {len(text) if text else 0}")
        if text and len(text) > 10:
            print(f"  Preview: {text[:200]}...")
        else:
            print("  ⚠️ No text found on this page")
        print()