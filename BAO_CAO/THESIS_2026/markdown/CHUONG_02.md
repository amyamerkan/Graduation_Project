# CHƯƠNG 2 CƠ SỞ LÝ THUYẾT VÀ CÔNG TRÌNH LIÊN QUAN

## 2.1 Giới thiệu

Chương này giải thích các lựa chọn kỹ thuật cần thiết để đọc và đánh giá hệ thống. Trọng tâm là biểu diễn tri thức, truy xuất từ vựng và ngữ nghĩa, gộp hạng, định tuyến và kiểm tra minh chứng. Việc lựa chọn lý thuyết tập trung vào những thành phần thực sự tham gia biểu diễn, truy xuất và kiểm tra dữ kiện của bài toán.

Hai sai lầm cần tránh là xem một truy vấn có cú pháp đúng như bảo đảm sự thật tuyệt đối và xem một vector có cosine cao như chứng minh quan hệ địa lý hoặc hiệu lực pháp lý. KG chỉ trả các sự kiện được mã hóa trong graph. Retriever chỉ xếp hạng tài liệu theo biểu diễn và phép đo đã chọn. Tính đúng của câu trả lời còn phụ thuộc chất lượng nguồn, ánh xạ thực thể, điều kiện truy vấn và khả năng đáp ứng đầy đủ câu hỏi.

## 2.2 Công trình liên quan

### 2.2.1 RAG và truy xuất ngữ nghĩa

Lewis và cộng sự nghiên cứu RAG như một hướng kết hợp tri thức tham số với truy xuất ngoài mô hình [1]. E5 cung cấp một họ encoder đa ngôn ngữ để biểu diễn query và passage [2]. Đồ án sử dụng các thành phần có sẵn này ở mức suy luận và lập chỉ mục. Không có thực nghiệm fine-tune E5 hoặc Qwen trong phạm vi kết quả được báo cáo.

Công trình về thư viện FAISS mô tả các thành phần phục vụ tìm kiếm vector [3]. Ở dự án này, vector đã chuẩn hóa được lập chỉ mục bằng IndexIDMap2 kết hợp IndexFlatIP. Vì vậy, không có cơ sở ghi rằng sản phẩm đang dùng IVF-PQ, HNSW hoặc tìm kiếm FAISS GPU chỉ vì các lựa chọn đó được nêu trong phần khảo sát. Cấu hình chỉ mục là một thành phần cần kiểm chứng từ file, không phải suy ra từ tên thư viện.

### 2.2.2 Kết hợp xếp hạng và đánh giá

RRF là một phương pháp gộp thứ hạng đã có trước đồ án [4]. BEIR cung cấp kinh nghiệm đánh giá nhiều họ retriever trên các bộ dữ liệu không đồng nhất [5]. Hai tham khảo này hỗ trợ quyết định thực nghiệm nhiều baseline và giữ ablation riêng, thay vì mặc định một phương án lai luôn tốt hơn tìm kiếm đơn lẻ.

RAGAs nghiên cứu các chiều đánh giá của hệ thống RAG [9]. Đồ án phân biệt chất lượng tài liệu truy xuất, tính được hỗ trợ của phát biểu và tính đúng ngoài đời. Việc chưa chạy đánh giá Faithfulness bằng người chấm hoặc bộ đánh giá độc lập được ghi nhận như một giới hạn. Cơ chế kiểm tra chuỗi và dữ kiện có cấu trúc trong code không tự trở thành điểm Faithfulness theo một giao thức bên ngoài.

### 2.2.3 Hỏi đáp địa lý và du lịch

GS-QA nghiên cứu câu hỏi trên dữ liệu không gian có nhiều kiểu thực thể, phép toán và dạng đáp án [6]. MapQA phiên bản về choropleth maps làm việc với hình ảnh bản đồ [7]. Tourism QA nghiên cứu tìm thực thể phù hợp từ dữ liệu đánh giá du lịch [8]. Chúng đặt ra các yêu cầu dữ liệu khác nhau; không thể chuyển tên gọi “MapQA” thành một tập câu hỏi văn bản tự tạo rồi coi đó là kết quả benchmark của công trình gốc.

Đồ án hiện có dữ liệu danh mục và bài giới thiệu điểm đến, chưa có bộ reviews tương ứng để thực nghiệm đúng nhiệm vụ của Tourism QA. Các câu hỏi bán kính và gần nhất cũng chưa có nguồn hình học và bộ thực thi để đối chiếu GS-QA. Khoảng trống này ảnh hưởng đến mức độ hoàn tất kế hoạch, nhưng không phủ nhận giá trị của bộ thực nghiệm miền hẹp đang có.

## 2.3 Phương pháp và các khái niệm sử dụng

### 2.3.1 RDF và truy vấn có điều kiện

RDF biểu diễn sự kiện theo bộ ba chủ thể, quan hệ và đối tượng. Với một phiên bản đơn vị hành chính, các quan hệ có thể lưu mã, tên, kiểu đơn vị, tỉnh trực thuộc, mốc snapshot và provenance. SPARQL cung cấp cách truy vấn các mẫu graph cùng điều kiện lọc [10]. Một kết quả đúng trong graph nghĩa là nó khớp mẫu và điều kiện của graph hiện tại; vẫn cần kiểm tra graph có phản ánh đúng nguồn hay không.

Mã cần được lưu như chuỗi. Chuỗi “00008” và số nguyên 8 không có cùng khả năng bảo toàn định danh trong danh mục. Cũng không nên gộp hai đơn vị chỉ vì cùng mã ở hai mốc khác nhau. Khóa logic của một bản ghi snapshot cần có ngữ cảnh thời gian và loại đơn vị, còn quan hệ chuyển đổi cũ–mới là một đối tượng thông tin riêng với khả năng chuyển một phần.

Một snapshot tại ngày t chỉ chứng minh những trường nguồn ghi tại t. Nếu không có khoảng hiệu lực đủ căn cứ, không được nội suy rằng các trường đó giữ nguyên đến mọi ngày tiếp theo. Với khoảng đóng có hai đầu, điều kiện thuộc khoảng có thể được kiểm tra trực tiếp. Với khoảng mở, một mốc được biết không tự xác nhận các ngày ngoài mốc đó. Những nguyên tắc này được mã hóa trong truy vấn và kiểm tra hậu truy xuất.

### 2.3.2 TF-IDF

TF-IDF tăng trọng số cho từ vừa xuất hiện trong tài liệu, vừa có khả năng phân biệt tài liệu so với corpus. Một dạng thường dùng là tf(t,d) nhân idf(t), sau đó chuẩn hóa vector để so sánh. Trong thí nghiệm, CountVectorizer tạo ma trận từ vựng và TfidfTransformer tạo biểu diễn chuẩn hóa. Câu hỏi và corpus được đưa qua cùng quy tắc chuẩn hóa phục vụ so khớp.

Ưu điểm của cách này là dễ kiểm tra và giữ tín hiệu của mã số, tên riêng hoặc từ hiếm. Hạn chế là những cách diễn đạt gần nghĩa nhưng ít từ chung có thể không được xếp cao. Dấu tiếng Việt được xử lý trong chuỗi phục vụ tìm kiếm; nội dung gốc của tài liệu vẫn được giữ. Không sử dụng bản chuẩn hóa để viết lại các câu nguồn.

### 2.3.3 BM25

BM25 tính mức phù hợp dựa trên tần suất từ, độ hiếm của từ và chuẩn hóa chiều dài tài liệu. Với tf là tần suất từ trong tài liệu, dl là độ dài và avgdl là độ dài trung bình, thành phần bão hòa được dùng trong thí nghiệm là tf × (k1 + 1) / [tf + k1 × (1 - b + b × dl / avgdl)]. Trọng số idf sử dụng log[1 + (N - df + 0,5) / (df + 0,5)].

Các giá trị k1 = 1,2 và b = 0,75 được cố định trong lượt đo. Đếm từ trên ma trận thưa cho phép tính điểm mà không cần lưu một vector đặc cho từng tài liệu. Đây là baseline thực thi trong script nghiên cứu; bộ tìm kiếm dự phòng FTS5 của ứng dụng là một đường triển khai khác và không được coi là cùng kết quả chỉ vì cùng sử dụng ý tưởng tìm kiếm từ vựng.

### 2.3.4 E5 và cosine

Encoder chuyển văn bản sang vector 768 chiều. Tiền tố query và passage được sử dụng theo cấu hình encoder của hệ thống; bước mở rộng thuật ngữ cũng cần được giữ nhất quán khi tái sử dụng vector. Nếu vector được chuẩn hóa về độ dài một, tích vô hướng bằng cosine. Do đó, IndexFlatIP có thể thực hiện tìm kiếm cosine khi cả hai phía tuân thủ cùng điều kiện chuẩn hóa.

Cosine là điểm tương tự của biểu diễn, không phải xác suất câu trả lời đúng. Một mã số ngắn có thể khó được encoder phân biệt, và hai đoạn mô tả gần nhau về ngữ nghĩa vẫn có thể thuộc hai tỉnh hoặc hai thời điểm khác nhau. Bộ lọc metadata và phép tra khóa chính xác được dùng để xử lý các điều kiện không nên giao hoàn toàn cho độ tương tự.

### 2.3.5 RRF và bộ lọc

Với một tài liệu d có thứ hạng r_i(d) trong danh sách thứ i, điểm RRF được tính bằng tổng 1 / [k + r_i(d)] trên những danh sách có d. Trong thí nghiệm, k = 60 và mỗi nguồn cung cấp tối đa 200 ứng viên chunk. Các chunk cùng tài liệu được gộp theo doc_id trước khi đánh giá tài liệu.

Gộp hạng có thể đưa tài liệu được cả hai nguồn hỗ trợ lên cao, nhưng cũng có thể kéo một kết quả ngữ nghĩa tốt xuống nếu kết quả đó ít được nhánh từ vựng hỗ trợ. Bộ lọc tỉnh có thể cải thiện câu hỏi danh sách điểm đến, song sẽ làm mất kết quả nếu tỉnh được phân giải sai. Vì vậy, từng bước thêm bộ lọc được xem là một cấu hình cần đo, không phải một cải tiến hiển nhiên.

### 2.3.6 Router và sinh có kiểm soát

Router có hai nhiệm vụ: dự đoán hướng xử lý kg/rag/hybrid và dự đoán miền administration/tourism. Cấu hình dùng TF-IDF từ, cụm ký tự và Logistic Regression, kết hợp quy tắc. Điểm do quy tắc gán không phải xác suất đã được hiệu chuẩn. Một confidence cao ở tầng định tuyến không thể thay cho sự tồn tại của bản ghi phù hợp trong nguồn.

Qwen3-0.6B được dùng ở đường chọn mệnh đề [11]. Máy chủ tạo danh sách mệnh đề được phép với claim_id, nội dung, loại minh chứng và các trường kiểm tra. Mô hình trả JSON chứa tối đa ba ID. Đầu ra ngoài registry, khóa trùng hoặc câu bổ sung không đúng hợp đồng bị loại. Phương pháp này khác với để LLM tự viết một bài tổng hợp dài rồi hy vọng bộ kiểm tra phát hiện mọi suy diễn sai.

## 2.4 Thực nghiệm minh họa và cách đọc chỉ số

Accuracy phân loại là tỷ lệ nhãn dự đoán đúng trên số câu có nhãn. Với route và domain, joint accuracy yêu cầu cả hai cùng đúng. F1 của bộ binding KG dựa trên true positive, false positive và false negative của các dòng kết quả có đáp án đầy đủ. Không lấy F1 đó thay cho F1 trả lời tự nhiên. Với một câu hỏi danh sách, đáp án chuẩn còn phải cho biết danh sách có đầy đủ hay chỉ có các phần tử dương đã biết.

Hit@k xác định có ít nhất một tài liệu dương trong k kết quả đầu. MRR@10 lấy nghịch đảo thứ hạng của tài liệu dương đầu tiên trong top 10, hoặc 0 nếu không có. nDCG@10 xét vị trí của các tài liệu dương so với thứ tự lý tưởng. Known-positive Recall@10 đo phần nhãn dương đã được tìm thấy, nhưng nhãn chưa đầy đủ sẽ giới hạn cách diễn giải mọi chỉ số này.

Với câu hỏi không có snapshot phù hợp, trả một tài liệu gần nghĩa có thể là một lỗi xử lý dù tài liệu đó tồn tại. Thực nghiệm vì thế báo tỷ lệ từ chối đúng riêng trên các ca không có snapshot. Một bộ tìm kiếm luôn trả kết quả thường không có cơ chế từ chối; so sánh với biến thể có điều kiện đồng thời đo thêm chính sách an toàn, chứ không chỉ đo khả năng xếp hạng.

Trong một ví dụ minh họa, nếu thứ hạng tài liệu đúng lần lượt là 1, 2 và không xuất hiện trong top 10, MRR bằng (1 + 1/2 + 0) / 3 = 0,5. Nếu một tập KG gồm 17 ca đều đạt, accuracy theo ca là 1,0, nhưng không thể suy ra 17 ca đã bao phủ mọi mã, ngày, địa danh và lỗi dữ liệu. Ví dụ này làm rõ lý do báo cáo luôn đi kèm mẫu số và phạm vi câu hỏi.

Khoảng bất định được ước lượng bằng bootstrap theo nhóm thực thể trong bộ silver test. Việc lấy mẫu theo nhóm tránh coi ba snapshot của cùng mã là ba quan sát hoàn toàn độc lập. Tuy nhiên, khoảng tin cậy thống kê vẫn chỉ áp dụng cho cơ chế xây dựng mẫu hiện có; nó không sửa được thiên lệch do câu hỏi tự sinh hoặc nhãn dương chưa được người độc lập duyệt.

Kết quả truy xuất thực tế của D1 cho MRR@10 lần lượt là 0,3769 với BM25, 0,6181 với E5 và 0,6127 với RRF trên silver test có nhãn dương. RRF không vượt E5 ở điểm tổng của lượt đo này; kết hợp nhiều nguồn điểm vì vậy vẫn cần được kiểm chứng theo tập câu và nhiệm vụ. Chi tiết điều kiện chạy và nhóm câu hỏi nằm ở Chương 5.

## 2.5 Kết luận

Chương 2 cung cấp các khái niệm để diễn giải kết quả ở đúng tầng: truy vấn graph, xếp hạng tài liệu, định tuyến và câu trả lời. Thiết kế kết hợp được xây trên những phương pháp có sẵn và phải chịu kiểm chứng bằng ablation. Các đặc tính như có nguồn, đúng mẫu câu hoặc khớp snapshot giúp tăng khả năng kiểm tra, nhưng không tạo ra một bảo đảm rằng dữ liệu nguồn đúng tuyệt đối. Cơ sở này dẫn tới cách tổ chức dữ liệu và phương pháp được trình bày trong Chương 3.
