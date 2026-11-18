# Công trình liên quan và khoảng trống

| Công trình hoặc chuẩn | Vai trò trong đồ án | Điều không được suy ra |
|---|---|---|
| RAG — Lewis et al., arXiv:2005.11401 | Cơ sở kết hợp truy xuất và mô hình ngôn ngữ | Không đồng nghĩa đã lặp lại huấn luyện của paper |
| Multilingual E5 — arXiv:2402.05672 | Encoder pretrained đa ngôn ngữ | Không fine-tune theo miền trong dự án |
| FAISS — arXiv:2401.08281 | Lập chỉ mục vector | Không có nghĩa đã dùng IVF-PQ/HNSW/GPU |
| RRF — Cormack et al., SIGIR 2009 | Gộp thứ hạng | Là phương pháp có sẵn, không phải phát minh của đồ án |
| BEIR — arXiv:2104.08663 | Tham khảo protocol nhiều retriever | Chưa chạy bộ benchmark này |
| RAGAs — ACL 2024 eacl-demo.16 | Phân biệt các chiều chất lượng RAG | Chưa có điểm Faithfulness độc lập |
| GS-QA — arXiv:2605.22811 | Hướng QA trên dữ liệu hình học | Chưa có engine và thực nghiệm tương ứng |
| MapQA — arXiv:2211.08545 | Hỏi đáp ảnh choropleth maps | Khác đầu vào văn bản hiện tại; tránh lẫn các bộ cùng tên |
| Tourism QA — arXiv:1909.03527 | QA đề xuất thực thể từ reviews | Corpus giới thiệu điểm đến chưa phải reviews benchmark |
| SPARQL 1.1 — W3C | Ngữ nghĩa truy vấn RDF | Cú pháp đúng không chứng minh nguồn đúng |

## Phát biểu đóng góp phù hợp

Có thể mô tả đóng góp là tổ chức dữ liệu Việt Nam theo phiên bản và tổ hợp truy xuất có ràng buộc mã/ngày/tỉnh, kèm thực nghiệm ablation. Chưa có cơ sở nói thuật toán mới toàn cầu, giảm ảo giác bao nhiêu phần trăm hoặc thắng mọi baseline. Mục tiêu nghiên cứu tiếp theo là nguồn chuẩn, gold độc lập, nhiều cách hỏi và đánh giá câu trả lời.

Danh mục đầy đủ gồm URL và ngày kiểm tra nằm ở TAI_LIEU_THAM_KHAO.md. Tài liệu mẫu được dùng để đối chiếu bố cục và phạm vi, không coi là nguồn xác nhận số liệu của sản phẩm.
