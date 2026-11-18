# Giao thức thực nghiệm và kiểm soát rò rỉ

D0 gồm 31.949 tài liệu; D1 gồm 38.993. Tập silver 263 câu chia 52 dev, 211 test; test có 188 câu dương và 23 câu không có snapshot. 16 câu thủ công là development set riêng. Nhóm thực thể theo mã hoặc tên được giữ cùng split. Bộ router D0 đóng băng cho cả hai corpus; router D1 được đánh giá riêng.

## Cấu hình

M1 TF-IDF; M2 BM25 (k1=1.2, b=0.75); M3 E5 pretrained; M4 BM25+E5/RRF (k=60); M5 M4+miền; M6 M5+tỉnh; M7 M6+khóa mã/ngày. Hai nguồn cung cấp tối đa 200 chunk, gộp doc_id và đánh giá top 10. Không fine-tune E5/Qwen, không chọn lại trọng số bằng test.

## Chỉ số

Hit@k và MRR tính trên câu có nhãn dương; nDCG xét tập dương top 10; Recall@10 là known-positive recall. Ca thiếu snapshot đo abstention accuracy riêng. Bootstrap 1.000 lượt theo 142 nhóm thực thể của các câu test dương. ranking_ms là tổng runner nhiều phương pháp, không phải độ trễ từng phương pháp. Không đổi MRR thành Accuracy trả lời.

## Cải thiện giao thức trước kết luận cuối

Giữ dữ liệu đóng băng trước khi gán nhãn; hai người duyệt nguồn và nhiều đáp án tương đương; thêm câu hỏi tự nhiên, ngày không rõ, tên trùng và chuyển một phần. Mẫu test kín mới không được dùng để lựa chọn cấu hình. Việc dữ liệu train có tên thực thể không phải bằng chứng fine-tune E5; vẫn cần chia nhóm đúng cho câu hỏi router nếu đánh giá router tổng quát.

Đánh giá nguồn độc lập với kiểm tra câu khớp nguồn. Khi corpus mới có quan sát tương đương chưa nằm trong positive IDs, ghi nhãn chưa đầy đủ, không tự kết luận nguồn mới sai. Cần báo kết quả D0/D1 trên cả toàn tập và nhóm câu hỏi cũ.
