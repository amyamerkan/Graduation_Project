# LỜI CẢM ƠN

Nhóm tác giả trân trọng cảm ơn giảng viên hướng dẫn TS. Trần Thanh Phước và Khoa Công nghệ thông tin, Trường Đại học Tôn Đức Thắng. Những yêu cầu về dữ liệu, đối chứng phương pháp và thực nghiệm giúp nhóm định hướng việc xây dựng sản phẩm gắn với bằng chứng có thể kiểm tra. Nhóm cũng ghi nhận đóng góp của các tác giả công trình, thư viện và nguồn dữ liệu được dẫn trong báo cáo.

Báo cáo trình bày các kết quả của hệ thống Tri Việt và những giới hạn còn cần hoàn thiện. Các ý kiến phản biện về chất lượng nhãn, nguồn hành chính và khả năng ứng dụng là cơ sở để nhóm tiếp tục cải thiện đồ án.

# CAM ĐOAN VỀ NGUỒN VÀ KẾT QUẢ

Nhóm tác giả chịu trách nhiệm rà soát nội dung, số liệu và các phát biểu trong báo cáo trước khi nộp. Các thành phần phương pháp, phần mềm và dữ liệu có sẵn được ghi nguồn; kết quả thực nghiệm được phân biệt với thiết kế đề xuất và công việc chưa thực hiện. Báo cáo không xem các phép kiểm thử trên tập nhỏ là bảo đảm tính đúng của mọi câu trả lời.

Nhóm tác giả

Nguyễn Anh Kiệt                         Trần Cao Phong

# TÓM TẮT

Đồ án xây dựng Tri Việt, hệ thống hỏi đáp văn bản về địa giới hành chính cũ–mới và du lịch Việt Nam theo kiến trúc KG, RAG và mô hình ngôn ngữ. Sản phẩm sử dụng RDFLib/SPARQL cho dữ kiện có cấu trúc, multilingual E5 và FAISS cho truy xuất, Qwen3-0.6B qua Transformers để chọn mệnh đề có minh chứng. Câu hỏi mã hành chính được kiểm tra theo mã, tỉnh và snapshot rồi trả theo mẫu không cần LLM.

Nghiên cứu so sánh bảy cấu hình trên D0 gồm 31.949 tài liệu và D1 gồm 38.993. D1 bổ sung 3.351 đoạn hành chính riêng biệt, 372 điểm du lịch và 3.321 dòng quan sát đối chiếu có ngày; tổng số điểm du lịch là 825. Tập silver có 263 câu, trong đó 211 test gồm 188 câu dương và 23 ca không có snapshot; 16 câu thủ công được giữ riêng. Trên D1 silver test, tổ hợp mã/ngày/tỉnh đạt MRR@10 0,9297, so với E5 0,6181 và RRF 0,6127. Trên bộ thủ công, RRF đạt 0,8854, cao hơn tổ hợp 0,8125. Kết quả hỗ trợ lợi ích có điều kiện, chưa chứng minh ưu thế tổng quát.

Đồ án có pipeline, graph, index, API và giao diện local; lần kiểm kê code đạt 353 unit test. Hạn chế gồm nhãn chưa được duyệt độc lập đầy đủ, dữ liệu thời gian theo mốc, chưa GIS bán kính và chưa thực nghiệm benchmark ngoài cùng đánh giá Faithfulness độc lập. Đóng góp được đặt ở tổ chức dữ liệu và phối hợp phương pháp cho bài toán, không khẳng định phát minh thuật toán toàn cầu.

Từ khóa: địa giới hành chính; hỏi đáp; Knowledge Graph; RAG; truy xuất lai; snapshot; du lịch Việt Nam.

# ABSTRACT

This thesis develops Tri Viet, a Vietnamese text question answering assistant for administrative changes and tourism. The system combines RDFLib and SPARQL, multilingual E5 embeddings with FAISS, and Qwen3-0.6B through Transformers for selecting evidence-backed claims. Simple administrative-code queries use a structured lookup and deterministic rendering with code, province and snapshot checks.

Seven retrieval configurations are compared on the existing corpus D0 with 31,949 documents and the expanded corpus D1 with 38,993 documents. The source-derived silver set contains 263 questions, including a 211-question test split with 188 answerable cases and 23 unsupported-date cases. A previous set of 16 manually authored development questions is reported separately. On D1 silver test, the constrained hybrid achieves MRR@10 of 0.9297, compared with 0.6181 for E5 and 0.6127 for RRF. On the manual development set, ordinary RRF achieves 0.8854 and exceeds the constrained method at 0.8125. These findings support task-specific benefits rather than universal superiority.

The contribution is a source-traceable dataset and an evaluated integration for the project domain. The results do not establish general factual accuracy or elimination of hallucinations. Independent annotation, external benchmarks, geometric queries and semantic answer evaluation remain necessary work.

Keywords: administrative geography; question answering; knowledge graph; retrieval augmentation; constrained retrieval; Vietnam tourism.
