from pathlib import Path
import re,json
from docx import Document
from docx.shared import Pt,Cm,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH,WD_BREAK,WD_TAB_ALIGNMENT,WD_TAB_LEADER
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
BASE=Path(__file__).resolve().parent; MD=BASE/'markdown'
pages=json.loads((BASE/'pagination_map.json').read_text()) if (BASE/'pagination_map.json').exists() else {}
doc=Document(); normal=doc.styles['Normal'];normal.font.name='Times New Roman';normal.font.size=Pt(13);normal.font.color.rgb=RGBColor(0,0,0)
# Remove decorative rules inherited from Word's built-in paragraph styles.
for style in doc.styles:
 for border in list(style.element.findall('.//' + qn('w:pBdr'))):
  border.getparent().remove(border)
pf=normal.paragraph_format;pf.line_spacing=1.5;pf.space_after=Pt(4);pf.first_line_indent=Cm(.8);pf.widow_control=True
for sty,size in [('Title',20),('Heading 1',16),('Heading 2',14),('Heading 3',13),('Caption',11)]:
 s=doc.styles[sty];s.font.name='Times New Roman';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0);s.font.bold=sty.startswith('Heading') or sty=='Title'
 s.paragraph_format.first_line_indent=Cm(0);s.paragraph_format.line_spacing=1.3;s.paragraph_format.space_before=Pt(10);s.paragraph_format.space_after=Pt(6);s.paragraph_format.keep_with_next=True
for name in ['Code']:
 if name not in doc.styles:
  from docx.enum.style import WD_STYLE_TYPE
  doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
 s=doc.styles[name];s.font.name='Courier New';s.font.size=Pt(8.5);s.paragraph_format.first_line_indent=Cm(0);s.paragraph_format.line_spacing=1.1;s.paragraph_format.space_after=Pt(1)
def config(sec):
 sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.left_margin=Cm(3);sec.right_margin=Cm(2);sec.top_margin=Cm(2.5);sec.bottom_margin=Cm(2.5);sec.footer_distance=Cm(1.2)
def numbering(sec,fmt,start):
 sec.footer.is_linked_to_previous=False
 p=sec.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0)
 fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');p._p.append(fld)
 el=OxmlElement('w:pgNumType');el.set(qn('w:fmt'),fmt);el.set(qn('w:start'),str(start));sec._sectPr.append(el)
config(doc.sections[0])
def text(p,t,bold=False,italic=False,size=None):
 t=t.replace('–','-').replace('—','-').replace('\u2011','-')
 # Plain, deterministic rendering; URLs remain readable text.
 t=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1 (\2)',t)
 parts=re.split(r'(\*\*.*?\*\*|`[^`]+`)',t)
 for part in parts:
  r=p.add_run(part[2:-2] if part.startswith('**') else part[1:-1] if part.startswith('`') else part)
  r.bold=True if bold or part.startswith('**') else None;r.italic=True if italic else None
  r.font.name='Times New Roman'
  if p.style.name=='Code': r.font.name='Courier New';r.font.size=Pt(8.5)
  if part.startswith('`'):r.font.name='Courier New';r.font.size=Pt(10)
  if size:r.font.size=Pt(size)
 return p
def paragraph(t='',style=None):
 p=doc.add_paragraph(style=style);text(p,t);p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY if not style else WD_ALIGN_PARAGRAPH.LEFT
 if re.search(r'\b[0-9a-f]{64}\b',t):p.alignment=WD_ALIGN_PARAGRAPH.LEFT
 return p
def heading(t,level=1):
 p=doc.add_paragraph(style='Heading '+str(level));text(p,t)
 if level==1:p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.page_break_before=True
 return p
def cover(inner=False):
 for t in ['TỔNG LIÊN ĐOÀN LAO ĐỘNG VIỆT NAM','TRƯỜNG ĐẠI HỌC TÔN ĐỨC THẮNG','KHOA CÔNG NGHỆ THÔNG TIN']:
  p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.line_spacing=1.15;p.paragraph_format.space_after=Pt(3);text(p,t,bold=t!='TỔNG LIÊN ĐOÀN LAO ĐỘNG VIỆT NAM',size=13)
 p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);p.add_run().add_picture(str(next((BASE/'assets').glob('university_logo.*'))),width=Cm(4.3));p.paragraph_format.space_after=Pt(24)
 for t in ['NGUYỄN ANH KIỆT - 52300123','TRẦN CAO PHONG - 52300144']:
  p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);text(p,t,bold=True,size=13)
 p=doc.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.space_before=Pt(38);p.paragraph_format.space_after=Pt(30);p.paragraph_format.line_spacing=1.35
 text(p,'HỆ THỐNG HỎI ĐÁP TỰ ĐỘNG\nVỀ ĐỊA GIỚI HÀNH CHÍNH MỚI\nVÀ THÔNG TIN DU LỊCH VIỆT NAM',bold=True,size=18)
 p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);text(p,'ĐỒ ÁN TỐT NGHIỆP',bold=True,size=18);p.paragraph_format.space_after=Pt(24)
 if inner:
  p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);text(p,'Người hướng dẫn\nTS. Trần Thanh Phước',size=13)
 p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.space_before=Pt(30 if inner else 65);text(p,'THÀNH PHỐ HỒ CHÍ MINH, NĂM 2026',bold=True,size=13)
cover();doc.add_page_break();cover(True)
front=doc.add_section(WD_SECTION_START.NEW_PAGE);config(front);numbering(front,'lowerRoman',1)
# Front-matter sections, each begins a fresh page except the very first.
front_text=(MD/'MO_DAU.md').read_text()
first=True
for block in re.split(r'(?m)^# ',front_text):
 if not block.strip():continue
 title,_,body=block.partition('\n')
 p=heading(title.strip(),1)
 if first:p.paragraph_format.page_break_before=False;first=False
 for para in body.strip().split('\n\n'):
  if para.strip():paragraph(para.strip().replace('\n',' '))
# Static TOC with verified page values from a previous render.
heading('MỤC LỤC',1)
parts=[*[f for f in sorted(MD.glob('CHUONG_*.md'))],MD/'TAI_LIEU_THAM_KHAO.md',MD/'PHU_LUC.md']
alltext='\n\n'.join(f.read_text() for f in parts)
toc=[]
for line in alltext.splitlines():
 if line.startswith('# ') or (line.startswith('## ') and re.match(r'\d\.\d\s',line[3:])):
  lev=0 if line.startswith('# ') else 1;label=line[2:] if lev==0 else line[3:];toc.append((lev,label))
for lev,label in toc:
 p=doc.add_paragraph();p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.left_indent=Cm(.45 if lev else 0);p.paragraph_format.line_spacing=1.0;p.paragraph_format.space_after=Pt(2);p.paragraph_format.space_before=Pt(3 if not lev else 0);p.paragraph_format.tab_stops.add_tab_stop(Cm(16),WD_TAB_ALIGNMENT.RIGHT,WD_TAB_LEADER.DOTS)
 text(p,label,bold=not lev,size=11);text(p,'\t'+str(pages.get(label,1)),size=11)
figures=[];tables=[]
for line in alltext.splitlines():
 m=re.match(r'!\[([^\]]+)\]',line)
 if m:figures.append(m[1])
 if re.match(r'Bảng [A-Z\d]+\.\d+',line):tables.append(line.strip())
heading('DANH MỤC HÌNH ẢNH',1)
for t in figures:paragraph(t+'\t'+str(pages.get(t,1)))
heading('DANH MỤC BẢNG BIỂU',1)
for t in tables:paragraph(t+'\t'+str(pages.get(t,1)))
heading('DANH MỤC TỪ VIẾT TẮT',1)
for t in ['API: Application Programming Interface - giao diện lập trình ứng dụng.','BM25: Best Matching 25 - phương pháp truy xuất từ vựng.','FAISS: thư viện tìm kiếm vector của Meta/Facebook AI Research.','KG: Knowledge Graph - đồ thị tri thức.','LLM: Large Language Model - mô hình ngôn ngữ lớn.','MRR: Mean Reciprocal Rank - trung bình nghịch đảo thứ hạng.','nDCG: normalized Discounted Cumulative Gain.','QA: Question Answering - hỏi đáp.','RAG: Retrieval-Augmented Generation - sinh có tăng cường truy xuất.','RDF: Resource Description Framework.','RRF: Reciprocal Rank Fusion - gộp nghịch đảo thứ hạng.','SPARQL: ngôn ngữ truy vấn RDF.','TF-IDF: Term Frequency - Inverse Document Frequency.','TITC: Trung tâm Thông tin du lịch.','UI: User Interface - giao diện người dùng.']:
 p=paragraph(t);p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.space_after=Pt(3)
heading('DANH MỤC KÝ HIỆU TOÁN HỌC',1)
for t in ['q: câu hỏi hoặc query.','d: tài liệu; t: từ trong công thức từ vựng, hoặc thời điểm tùy ngữ cảnh.','N: số tài liệu/chunk của corpus đang xét.','tf(t,d): số lần từ t xuất hiện trong d.','df(t): số tài liệu chứa t.','dl, avgdl: độ dài tài liệu và trung bình corpus.','k1, b: tham số BM25; k = 60: hằng số RRF trong thực nghiệm.','r_i(d): thứ hạng của d trong danh sách thứ i.','D0, D1: corpus trước mở rộng và corpus nghiên cứu mở rộng.','TP, FP, FN: số binding dương đúng, dương sai và dương bị bỏ sót.','MRR@10: trung bình nghịch đảo thứ hạng của tài liệu dương đầu tiên trong top 10.','CI: khoảng tin cậy bootstrap trong phạm vi bộ câu hỏi được đo.']:
 paragraph(t).paragraph_format.first_line_indent=Cm(0)
body=doc.add_section(WD_SECTION_START.NEW_PAGE);config(body);numbering(body,'decimal',1)
# Render Markdown blocks with proper Word structures.
def render_table(lines):
 rows=[[c.strip() for c in l.strip().strip('|').split('|')] for l in lines];rows=[rows[0]]+rows[2:];n=len(rows[0]);width=16
 widths=[width/n]*n
 if n==2:widths=[5,11]
 if n==3:widths=[8,4,4]
 if n==4:widths=[7,3,3,3]
 if n==5:widths=[6,2.5,2.5,2.5,2.5]
 if n==6:widths=[6,2,2,2,2,2]
 if rows[0][0]=='Mã': widths=[1.4,9,5.6] if n==3 else widths
 if n==3 and rows[0][0]=='Ca': widths=[1.5,7,7.5]
 tb=doc.add_table(rows=0,cols=n);tb.alignment=WD_TABLE_ALIGNMENT.CENTER;tb.autofit=False
 for col,w in zip(tb.columns,widths):col.width=Cm(w)
 for ri,row in enumerate(rows):
  cells=tb.add_row().cells
  for j,c in enumerate(cells):
   c.width=Cm(widths[j]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   tcpr=c._tc.get_or_add_tcPr();m=OxmlElement('w:tcMar')
   for side in ['top','left','bottom','right']:
    el=OxmlElement('w:'+side);el.set(qn('w:w'),'45' if n==6 and side in {'top','bottom'} else '60');el.set(qn('w:type'),'dxa');m.append(el)
   tcpr.append(m);b=OxmlElement('w:tcBorders')
   for side in ['top','left','bottom','right']:
    el=OxmlElement('w:'+side);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');b.append(el)
   tcpr.append(b)
   if ri==0:
    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E7ECF0');tcpr.append(shade)
   p=c.paragraphs[0];p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.line_spacing=1.05 if n==6 else 1.1;p.paragraph_format.space_after=Pt(1 if n==6 else 2);p.paragraph_format.space_before=Pt(1 if n==6 else 2)
   p.alignment=WD_ALIGN_PARAGRAPH.LEFT if j==0 or not re.fullmatch(r'[\d.,;\[\] -]+',row[j]) else WD_ALIGN_PARAGRAPH.CENTER
   text(p,row[j].replace('nDCG@10','nDCG\n@10'),bold=ri==0,size=10.5)
  trpr=cells[0]._tc.getparent().get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
  if ri==0:rep=OxmlElement('w:tblHeader');trpr.append(rep)
 paragraph('').paragraph_format.space_after=Pt(2)
lines=alltext.splitlines();i=0;code=False;first_body=True
while i<len(lines):
 line=lines[i].strip()
 if not line:i+=1;continue
 if line.startswith('```'):code=not code;i+=1;continue
 if code:paragraph(line,'Code');i+=1;continue
 if line.startswith('|'):
  group=[]
  while i<len(lines) and lines[i].strip().startswith('|'):group.append(lines[i]);i+=1
  render_table(group);continue
 m=re.match(r'^(#{1,3})\s+(.+)',line)
 if m:
  p=heading(m[2],len(m[1]))
  if m[2].startswith('5.4.3 '):p.paragraph_format.page_break_before=True
  if first_body:p.paragraph_format.page_break_before=False;first_body=False
  i+=1;continue
 m=re.match(r'!\[([^\]]+)\]\(([^)]+)\)',line)
 if m:
  image_path=(MD/m[2]).resolve();p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.first_line_indent=Cm(0);p.paragraph_format.keep_with_next=True
  p.add_run().add_picture(str(image_path),width=Cm(15.5));p=paragraph(m[1],'Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.keep_with_next=False;i+=1;continue
 if re.match(r'Bảng [A-Z\d]+\.\d+',line):
  p=paragraph(line,'Caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER;i+=1;continue
 paragraph(line);i+=1
# OOXML language and fixed black type.
for sty in doc.styles:
 if sty.type==1:
  rp=sty.element.get_or_add_rPr();rf=rp.find(qn('w:rFonts'))
  if rf is not None:
   for key in list(rf.attrib):
    if 'Theme' in key: del rf.attrib[key]
   for key in ['ascii','hAnsi','cs','eastAsia']:rf.set(qn('w:'+key),'Courier New' if sty.name=='Code' else 'Times New Roman')
  lang=OxmlElement('w:lang');lang.set(qn('w:val'),'vi-VN');rp.append(lang)
doc.core_properties.title='Hệ thống hỏi đáp tự động về địa giới hành chính mới và thông tin du lịch Việt Nam'
doc.core_properties.author='Nguyễn Anh Kiệt; Trần Cao Phong';doc.core_properties.subject='Đồ án tốt nghiệp - nghiên cứu 30–31/10 và kiểm thử tích hợp 18/11/2026'
out=BASE/'output/docx/Bao_cao_Do_an_Tot_nghiep_Tri_Viet_2026.docx';doc.save(out)
(BASE/'document_structure.json').write_text(json.dumps({'toc':[x[1] for x in toc],'figures':figures,'tables':tables},ensure_ascii=False,indent=2))
print(out)
