# CHƯƠNG 6 KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 6.1 Giới thiệu

Chương cuối tổng hợp kết quả theo mục tiêu nghiên cứu và theo yêu cầu sản phẩm. Việc tổng hợp không thay đổi phạm vi của những số đo trước đó. Chương này xác định điều đã chứng minh được, giới hạn còn tồn tại và các bước có thể đưa bản nghiên cứu tới một phiên bản ứng dụng được đánh giá đầy đủ hơn.

Điểm cốt lõi của đồ án là giữ điều kiện câu hỏi trong toàn bộ chuỗi xử lý. Một hệ thống hữu ích không chỉ tìm được đoạn văn liên quan mà còn phải biết đoạn đó có xác nhận mã, tỉnh, thời điểm và đối tượng được hỏi hay không. Các lỗi thực tế về mã địa phương và câu hỏi bán kính đã giúp làm rõ sự khác nhau giữa trích dẫn, kiểm tra điều kiện và khả năng thực thi.

## 6.2 Công trình liên quan và vị trí đóng góp

Các thành phần RAG, E5, FAISS và RRF được kế thừa từ các công trình và thư viện có sẵn [1–4]. Các nghiên cứu đánh giá [5,9] giúp định hướng việc tách lớp metric và kiểm tra những tình huống không thuận lợi. GS-QA, MapQA và Tourism QA [6–8] xác định những hướng mở rộng có nhiệm vụ khác với tập câu hỏi văn bản hiện tại.

Đóng góp ở mức đồ án là một tổ hợp có thể kiểm tra trong bài toán Việt Nam, gồm dữ liệu theo phiên bản, đường tra khóa hành chính, lọc tỉnh, gộp hạng và kiểm tra mệnh đề. Thực nghiệm ablation cho phép chỉ ra phần nào của tổ hợp có lợi cho nhóm nào. Chưa có khảo sát toàn diện để tuyên bố đây là thuật toán mới trên thế giới, cũng chưa có benchmark ngoài miền đủ để suy ra tính tổng quát của phương pháp.

Vì Qwen3-0.6B chủ yếu chọn mệnh đề, sản phẩm ưu tiên khả năng truy nguyên hơn tính linh hoạt viết dài. Đây là một lựa chọn triển khai có lợi và có chi phí. Nó hạn chế phát biểu tự do không có trong nguồn, nhưng cũng hạn chế khả năng tổng hợp những câu trả lời phong phú từ nhiều đoạn. Đánh giá tương lai cần đo cả mặt hữu ích này thay vì chỉ đo khả năng ngăn lỗi.

## 6.3 Tổng kết phương pháp và dữ liệu

### 6.3.1 Đối chiếu ba yêu cầu nghiên cứu

Đối với yêu cầu thứ nhất, đồ án đã sử dụng dữ liệu nền có sẵn và cài đặt các baseline truy xuất để có kết quả ban đầu. Bộ dữ liệu dự án trước mở rộng được ký hiệu D0; nguồn cộng đồng và nguồn chính thức được ghi rõ. Các phép đo chưa được ghi nhầm thành kết quả benchmark công khai độc lập.

Đối với yêu cầu thứ hai, D1 bổ sung 372 điểm du lịch và 3.351 đoạn hành chính riêng biệt, cùng 3.321 dòng quan sát NSO có ngày riêng. Corpus D1 có 38.993 tài liệu; dữ liệu D0 được bảo toàn. Bảy cấu hình được chạy trên cả hai corpus, có bảng chỉ các câu hỏi cũ để phân biệt hiệu ứng phủ dữ liệu với thay đổi thứ hạng.

Đối với yêu cầu thứ ba, biến thể đề xuất kết hợp tín hiệu từ vựng, ngữ nghĩa, miền, tỉnh và điều kiện mã/ngày. Nó được so sánh với các cấu hình bỏ bớt thành phần trên tập phát triển của dự án. Đây là kết quả sơ bộ về một phương án lai; yêu cầu khẳng định giá trị tổng quát vẫn cần thêm test kín và nhãn độc lập.

### 6.3.2 Sản phẩm phần mềm

Tri Việt có pipeline dữ liệu, ontology và graph RDF, mười mẫu SPARQL, chỉ mục vector cùng metadata, router, bộ giải quyết hội thoại, dịch vụ trả lời và giao diện local. Đường tra mã không dùng RAG fallback khi thiếu KG và không cần gọi LLM. Đường mô tả có trích dẫn và kiểm tra mệnh đề trong phạm vi cho phép.

Bản nghiên cứu mới được giữ riêng với các artifact huấn luyện, chỉ mục, câu hỏi, kết quả chi tiết, phiếu duyệt nhãn và script tái lập. Việc tách release giúp kiểm tra mà không làm thay dữ liệu app đang được sử dụng. Đưa D1 và phương pháp nghiên cứu vào ứng dụng cần một bước tích hợp, kiểm thử end-to-end và kiểm soát rollback riêng.

### 6.3.3 Giới hạn cần duy trì

Timeline mới có các mốc cụ thể, chưa phải hồ sơ lịch sử liên tục của mọi đơn vị. Graph lưu quan hệ hành chính, chưa có đầy đủ polygon, tọa độ và phép toán khoảng cách. Các đoạn nghị quyết được giữ như văn bản; chưa xác nhận tự động từng phần diện tích chuyển đổi và văn bản căn cứ của mọi cạnh. Các điểm du lịch có độ phủ không đều và địa chỉ có thể dùng cấp hành chính cũ.

Tập silver có thiên lệch từ khuôn câu và nguồn tạo nhãn. Bộ thủ công chỉ có 16 câu và đã được dùng phát triển. Các artifact kiểm thử app là bằng chứng theo phiên bản, không phải điểm chấm độc lập cho toàn bộ dữ liệu. Hệ thống chưa có bảo đảm triển khai công khai về tài khoản, phân quyền, rate limit hoặc tải đồng thời nhiều người dùng.

## 6.4 Tổng hợp thực nghiệm và kế hoạch hoàn thiện

### 6.4.1 Kết luận từ số đo

Các số đo cho phép trả lời RQ1 theo từng nhóm: E5 phù hợp hơn với một số mô tả, trong khi mã/ngày cần tra cứu có điều kiện. RQ2 cho thấy dữ liệu mới tăng độ phủ nhưng không bảo đảm mọi câu cũ tăng điểm. RQ3 cho thấy tổ hợp có điều kiện có lợi trên tập silver, song RRF thường lại tốt hơn trên 16 câu thủ công. RQ4 cho thấy phần lõi đã có bằng chứng hoạt động, còn benchmark công khai, hình học và đánh giá ngữ nghĩa độc lập chưa hoàn tất.

Không có kết luận rằng ảo giác đã bị triệt tiêu. Kết quả hiện tại chứng minh một số rào kiểm tra có thể ngăn các lớp lỗi cụ thể và trả phản hồi thiếu bằng chứng thay vì suy đoán. Muốn định lượng mức giảm phát biểu không có căn cứ, cần cùng một tập câu hỏi và cùng cấu hình mô hình với thí nghiệm bật/tắt cơ chế kiểm tra, chấm mệnh đề và đo tỷ lệ từ chối.

Các bằng chứng định lượng được tổng hợp gồm 353 unit test, 17/17 ca KG development và MRR@10 0,9297 của tổ hợp trên silver test D1. Bộ 16 câu thủ công lại cho RRF thường 0,8854 và tổ hợp 0,8125. Việc đặt hai kết quả cạnh nhau giới hạn kết luận vào từng giao thức, thay vì chọn một tỷ lệ thuận lợi làm đại diện toàn bộ sản phẩm.

### 6.4.2 Ưu tiên đánh giá khoa học

Ưu tiên đầu tiên là duyệt nhãn bằng nguồn. Người duyệt cần xem các câu hỏi và tài liệu trong annotation_review.csv, ghi nhận nhiều đáp án tương đương và chỉ rõ trường hợp nguồn không đủ căn cứ. Một tập câu hỏi tự nhiên mới cần được giữ kín, tách theo thực thể và thời điểm phù hợp, không dùng lại để điều chỉnh tham số.

Ưu tiên thứ hai là tổ chức đánh giá câu trả lời. Rubric cần tách tính đúng của dữ kiện, mức hỗ trợ từng phát biểu, mức trả lời đủ, sự phù hợp của trích dẫn và cách từ chối. Có thể dùng thang chấm có định nghĩa và hai người đánh giá để đo độ đồng thuận. Điểm tự động hoặc LLM judge nếu bổ sung phải được đối chiếu với một mẫu người chấm, không coi công cụ tự chấm là chuẩn vàng mặc định.

Ưu tiên thứ ba là xác lập một benchmark bên ngoài. Nhóm cần chọn đúng phiên bản GS-QA, MapQA hoặc Tourism QA, đọc giấy phép và chuẩn bị adapter nhiệm vụ. Một benchmark đọc ảnh bản đồ không phù hợp đường văn bản hiện tại nếu chưa bổ sung mô hình thị giác. Kết quả trên bộ công khai phải có tập câu, protocol và output riêng, không đổi tên bộ silver đang có.

### 6.4.3 Ưu tiên dữ liệu và truy vấn địa lý

Đối với thời gian, cần liên kết nguồn hiệu lực với từng sự kiện thay vì chỉ có thuộc tính chung của node. Những trường như thời điểm ban hành, thời điểm có hiệu lực và phạm vi chuyển một phần cần được kiểm tra độc lập. Khi dữ liệu cho phép, hệ thống mới có thể trả lời một số ngày ngoài các snapshot hiện tại.

Đối với bán kính, cần xác định mốc xuất phát và loại khoảng cách. Khoảng cách đường thẳng, đường đi và thời gian di chuyển là các câu hỏi khác nhau. Dữ liệu tọa độ hoặc hình học phải có hệ quy chiếu và nguồn; phép toán phải có kiểm thử bằng các điểm chuẩn. Chỉ khi các điều kiện đó được đáp ứng mới có thể xem câu “gần nhất trong 5 km” là chức năng đã thực hiện.

Đối với du lịch, cần tăng độ phủ ở các tỉnh có ít bản ghi, giữ cả tên tỉnh nguồn và quan hệ ánh xạ có căn cứ, tránh suy ra địa chỉ xã mới từ một tỉnh mới. Có thể bổ sung loại trải nghiệm và thuộc tính phục vụ người dùng, nhưng những trường như giờ mở cửa, giá vé và điều kiện tiếp cận cần cơ chế cập nhật riêng vì dễ thay đổi.

### 6.4.4 Ưu tiên kỹ thuật và bàn giao

D1 đã được kiểm thử cô lập ngày 18/11/2026 với 353 unit test, 65 ca HTTP và 33 kiểm tra UI đạt; manifest ghi hash graph, corpus, router và chỉ mục tương ứng. Đo lặp ba câu phát triển, mỗi câu năm lần sau warmup, bổ sung bằng chứng độ trễ sơ bộ theo từng đường xử lý. Cần tiếp tục duyệt nội dung và ca giảm điểm trước khi thay release mặc định; các kiểm tra này chưa thay được nghiệm thu chất lượng độc lập hoặc đo tải đồng thời.

Các đầu việc cuối của kế hoạch gồm tối ưu có kiểm chứng, hoàn thiện báo cáo, đóng gói source, hướng dẫn sử dụng, slide, video demo và diễn tập bảo vệ. Bộ Markdown của đợt này cung cấp bảng đối chứng, protocol, kết quả và backlog; không có bằng chứng để đánh dấu slide, video hoặc bảo vệ đã hoàn thành. Thời hạn trong kế hoạch được giữ như mốc dự kiến, không biến thành lịch sử hoàn thành giả.

## 6.5 Kết luận

Đồ án đã xây dựng một trợ lý hỏi đáp miền hẹp có thể chạy local và một bộ thực nghiệm truy xuất có đối chứng trên dữ liệu nền cùng dữ liệu mở rộng. Giá trị chính nằm ở việc giữ điều kiện hành chính theo thời gian, tách các loại minh chứng và kiểm tra đầu ra trước khi trình bày. Kết quả cũng cho thấy giới hạn của chính phương án lai: nó có ích cho một số kiểu câu nhưng chưa là lựa chọn tốt nhất cho mọi tình huống.

Bản báo cáo kết thúc ở mức kết quả đã có thể kiểm tra: dữ liệu có provenance, artifacts huấn luyện và chỉ mục, các bảng số đo, ca lỗi và kế hoạch hoàn thiện. Để đạt một kết luận mạnh hơn về hiệu quả ngoài thực tế, cần tiếp tục gán nhãn độc lập, thực nghiệm benchmark phù hợp, đánh giá câu trả lời và kiểm thử bản tích hợp cuối. Việc giữ các giới hạn này rõ ràng làm cho đóng góp của đồ án có thể được đánh giá và tiếp tục phát triển một cách đáng tin cậy.
