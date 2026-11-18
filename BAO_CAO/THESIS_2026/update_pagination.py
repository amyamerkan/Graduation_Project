from pathlib import Path
import sys,json,re,unicodedata
from pypdf import PdfReader
BASE=Path(__file__).resolve().parent
pdf=Path(sys.argv[1]);reader=PdfReader(pdf);structure=json.loads((BASE/'document_structure.json').read_text())
def norm(s):return ''.join(re.findall(r'\w+',unicodedata.normalize('NFC',s).casefold()))
pages=[norm(p.extract_text() or '') for p in reader.pages]
start=next(i for i,t in enumerate(pages) if norm('CHƯƠNG 1 MỞ ĐẦU') in t and i>8)
labels=structure['toc']+structure['figures']+structure['tables'];mapping={};missing=[]
for label in labels:
 found=next((i for i,t in enumerate(pages) if i>=start and norm(label) in t),None)
 if found is None:missing.append(label)
 else:mapping[label]=found-start+1
assert not missing,missing
old=json.loads((BASE/'pagination_map.json').read_text()) if (BASE/'pagination_map.json').exists() else {}
(BASE/'pagination_map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2))
print({'pdf_pages':len(reader.pages),'body_starts_pdf_page':start+1,'labels':len(labels),'mapping_stable':old==mapping})
