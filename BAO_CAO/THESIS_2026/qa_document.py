from pathlib import Path
import argparse,json,re,hashlib,unicodedata
import pdfplumber
from PIL import Image,ImageDraw
BASE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--render-dir', type=Path, default=BASE/'tmp/render_submission')
args=parser.parse_args()
render=args.render_dir;pdf=next(render.glob('*.pdf'))
report={'pdf':str(pdf),'checks':{},'page_warnings':[]}
chapters=sorted((BASE/'markdown').glob('CHUONG_*.md'))
report['checks']['six_chapters']=len(chapters)==6
for i,f in enumerate(chapters,1):
 txt=f.read_text(); heads=re.findall(r'^## (.+)$',txt,re.M)
 report['checks'][f'chapter_{i}_five_sections']=len(heads)==5 and all(h.startswith(f'{i}.{j}') for j,h in enumerate(heads,1))
full=(BASE/'markdown/BAO_CAO_DO_AN_TOT_NGHIEP.md').read_text()
report['checks']['no_unresolved_markers']=not re.search(r'\{\{[^}]+\}\}|TODO|\[điền',full,re.I)
links=[]
for f in (BASE/'markdown').glob('*.md'):
 for link in re.findall(r'\]\(([^)]+)\)',f.read_text()):
  if not re.match(r'^(?:https?://|#)',link):links.append((f.name,link,(f.parent/link).exists()))
report['checks']['local_markdown_links_exist']=all(x[2] for x in links)
with pdfplumber.open(pdf) as d:
 report['page_count']=len(d.pages);report['page_stats']=[]
 for i,p in enumerate(d.pages,1):
  words=p.extract_words();t=p.extract_text() or '';outside=[w['text'] for w in words if w['x0']<50 or w['x1']>p.width-43 or w['top']<40 or w['bottom']>p.height-28]
  if outside:report['page_warnings'].append({'page':i,'outside_safe_page_bounds':outside})
  if i>=12 and len(t)<350:report['page_warnings'].append({'page':i,'sparse_text_chars':len(t),'note':'Check image or ending section visually'})
  if '\ufffd' in t or '\u25a0' in t:report['page_warnings'].append({'page':i,'missing_glyph':True})
  report['page_stats'].append({'page':i,'chars':len(t),'words':len(words),'first_line':t.splitlines()[0] if t else ''})
 report['checks']['page_count_matches_pngs']=len(list(render.glob('page-*.png')))==len(d.pages)
 report['checks']['no_replacement_glyphs']=not any(x.get('missing_glyph') for x in report['page_warnings'])
# Native-resolution review sheets: no page scaling.
files=sorted(render.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]));contacts=BASE/'tmp/review_sheets';contacts.mkdir(exist_ok=True)
for first in range(0,len(files),4):
 images=[Image.open(p).convert('RGB') for p in files[first:first+4]];w=max(im.width for im in images);h=max(im.height for im in images)
 sheet=Image.new('RGB',(w*2,h*2+50),'#dddddd');dr=ImageDraw.Draw(sheet)
 for j,im in enumerate(images):sheet.paste(im,((j%2)*w,(j//2)*h+50))
 dr.text((10,12),f'PDF pages {first+1}-{min(first+4,len(files))}; native 100 dpi',fill='black')
 sheet.save(contacts/f'sheet-{first//4+1:02}.png')
report['pdf_sha256']=hashlib.sha256(pdf.read_bytes()).hexdigest()
report['checks']['required_identity']=all(x in full for x in ['Nguyễn Anh Kiệt','52300123','Trần Cao Phong','52300144','TS. Trần Thanh Phước'])
report['visual_review']='pending native-resolution sheet review'
(BASE/'qa_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print({k:report[k] for k in ['page_count','checks','page_warnings']})
