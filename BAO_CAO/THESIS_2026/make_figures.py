from pathlib import Path
import sys,json
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'tmp/pydeps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch
font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Times New Roman.ttf')
plt.rcParams.update({'font.family':'Times New Roman','font.size':14,'savefig.dpi':200})
r=json.loads((BASE.parents[1]/'artifacts/research_expansion_2026-10-30/experiment_report.json').read_text())
methods=['tfidf','bm25','dense_e5','rrf','rrf_domain_province','proposed_temporal_province_rrf'];names=['TF-IDF','BM25','E5','RRF','RRF + tỉnh','Lai mã/ngày/tỉnh']
fig,axes=plt.subplots(1,2,figsize=(8.5,4.8),sharey=True)
for ax,key,title in zip(axes,['summary','manual_development'],['Silver test có nhãn dương (n=188)','Bộ phát triển thủ công (n=16)']):
 vals=[r['datasets']['expanded'][key][m]['test']['mrr_at_10'] if key=='summary' else r['datasets']['expanded'][key][m]['mrr_at_10'] for m in methods]
 bars=ax.barh(names[::-1],vals[::-1],color=['#24475b' if m=='proposed_temporal_province_rrf' else '#8a9fab' for m in methods][::-1])
 ax.set_xlim(0,1.09);ax.set_xlabel('MRR@10');ax.set_title(title,fontsize=14);ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
 for b,v in zip(bars,vals[::-1]):ax.text(v+.01,b.get_y()+b.get_height()/2,f'{v:.3f}',va='center',fontsize=12)
fig.tight_layout();fig.savefig(BASE/'assets/mrr_comparison.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4.8));import numpy as np
kinds=['temporal_code','destination','merger_clause','province_destinations'];labels=['Mã và ngày','Điểm đến','Đoạn sắp xếp','Theo tỉnh']
for off,m,col in [(-.25,'dense_e5','#8398a7'),(0,'rrf','#c1cbd2'),(.25,'proposed_temporal_province_rrf','#24475b')]:
 vals=[r['datasets']['expanded']['slices'][m][k]['ndcg_at_10' if k=='province_destinations' else 'mrr_at_10'] for k in kinds]
 ax.bar(np.arange(4)+off,vals,.24,label={'dense_e5':'E5','rrf':'RRF','proposed_temporal_province_rrf':'Lai mã/ngày/tỉnh'}[m],color=col)
ax.set_xticks(range(4),labels);ax.set_ylim(0,1.1);ax.set_ylabel('MRR@10; nhóm tỉnh dùng nDCG@10');ax.legend(loc='upper right',fontsize=12);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(BASE/'assets/task_results.png');plt.close(fig)
fig,ax=plt.subplots(figsize=(10,6.7));ax.axis('off');ax.set_xlim(0,10);ax.set_ylim(0,10)
def box(x,y,w,h,text,color='#eef1f3'):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.1',facecolor=color,edgecolor='#40545e',linewidth=1));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=16)
def arrow(a,b):ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','color':'#40545e'})
box(2.4,8.7,5.2,.8,'Giao diện web và FastAPI')
box(2.4,7.2,5.2,.8,'Hội thoại • nhận diện mã • router • kế hoạch')
arrow((5,8.7),(5,8))
box(.3,5.4,3.8,1,'RDFLib / SPARQL\nMã • tỉnh • snapshot')
box(5.9,5.4,3.8,1,'E5 / FAISS + SQLite\nĐoạn văn • nguồn • miền')
arrow((4,7.2),(2.2,6.4));arrow((6,7.2),(7.8,6.4));arrow((4.1,5.9),(5.9,5.9))
box(.3,3.6,3.8,1,'Tra mã trực tiếp theo mẫu\nkhông gọi LLM')
box(5.9,3.6,3.8,1,'Qwen chọn claim_id\nkhông tự thêm phát biểu')
arrow((2.2,5.4),(2.2,4.6));arrow((7.8,5.4),(7.8,4.6))
box(2.4,1.8,5.2,1,'Đọc lại KG • kiểm tra mệnh đề\ntrả lời / một phần / từ chối / làm rõ')
arrow((2.2,3.6),(3.6,2.8));arrow((7.8,3.6),(6.4,2.8))
ax.text(5,.7,'D0 là app hiện tại; bảy cấu hình truy xuất D1 ở harness nghiên cứu riêng',ha='center',fontsize=12)
fig.tight_layout();fig.savefig(BASE/'assets/architecture.png');plt.close(fig)
print('Figures generated')
