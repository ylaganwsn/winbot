from pypdf import PdfReader

reader = PdfReader("sample-cost-estimate.pdf")

print("Total pages:", len(reader.pages))

for number, page in enumerate(reader.pages, start=1):
    text = page.extract_text()
    print(f"\n--- Page {number} ---")
    print(text[:200])