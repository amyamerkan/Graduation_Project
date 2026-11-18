# CHƯƠNG 1 MỞ ĐẦU

## 1.1 Giới thiệu

Việc tra cứu một địa danh Việt Nam ngày càng đòi hỏi xác định cả tên gọi, cấp hành chính và thời điểm mà thông tin được ghi nhận. Cùng một mã đơn vị có thể xuất hiện ở nhiều danh mục lịch sử với tên khác nhau. Một địa chỉ du lịch trong bài giới thiệu cũ có thể vẫn dùng huyện hoặc tỉnh trước sắp xếp, trong khi người dùng hỏi bằng tên tỉnh hiện tại. Nếu hệ thống chỉ tìm những đoạn văn gần nghĩa và để mô hình ngôn ngữ suy diễn phần còn thiếu, câu trả lời có thể trôi chảy nhưng không đáp ứng điều kiện người dùng yêu cầu.

Đồ án nghiên cứu và xây dựng Tri Việt, hệ thống hỏi đáp bằng tiếng Việt về địa giới hành chính cũ và mới cùng thông tin du lịch Việt Nam. Chương này xác định vấn đề, câu hỏi nghiên cứu, phạm vi thực hiện và loại bằng chứng cần có. Việc làm rõ phạm vi ngay từ đầu giúp đánh giá sản phẩm theo khả năng thực tế, thay vì đồng nhất một giao diện trò chuyện hoạt động được với một hệ thống đã giải quyết đầy đủ bài toán không gian và thời gian.

Một lỗi thực tế có tính điển hình là câu hỏi “00008 thuộc địa phương nào” từng nhận một địa chỉ điểm du lịch ở Điện Biên. Đoạn địa chỉ đó có nguồn trong corpus nhưng không xác nhận mã 00008. Như vậy, có trích dẫn chưa đủ để chứng minh câu trả lời đúng với câu hỏi. Sau sửa, luồng tra mã bắt buộc lấy bản ghi KG, giữ số 0 đầu, kiểm tra điều kiện và dựng câu trực tiếp. Trên snapshot đang lưu ngày 24/10/2026, mã này gắn với Phường Ngọc Hà, Thành phố Hà Nội. Đây là kết luận trong phạm vi danh mục của ứng dụng, không phải xác nhận pháp lý độc lập cho mọi thời điểm.

Vấn đề thứ hai thể hiện qua câu hỏi “Điểm tham quan nào gần Hội An nhất trong bán kính 5 km?”. Quan hệ thuộc tỉnh và phần mô tả địa chỉ không đủ để tính bán kính. Cần có tọa độ, mốc xuất phát, hệ quy chiếu và phép tính khoảng cách phù hợp. Phiên bản hiện tại chủ động từ chối xác nhận điều kiện này. Phản hồi đó là biểu hiện của ranh giới năng lực đã được thiết kế, đồng thời là một khoảng trống cần ghi nhận so với kế hoạch ban đầu.

## 1.2 Công trình liên quan

RAG kết hợp bộ truy xuất với mô hình sinh để sử dụng tri thức bên ngoài trọng số mô hình [1]. Đồ án vận dụng nguyên tắc dựa vào minh chứng, nhưng không triển khai lại toàn bộ thiết kế huấn luyện của công trình gốc. Trong sản phẩm, LLM chủ yếu chọn mã mệnh đề do máy chủ chuẩn bị, còn câu tra mã hành chính có đường trả lời theo mẫu không cần LLM. Thiết kế này thu hẹp khả năng diễn giải tự do để tăng khả năng kiểm tra từng phát biểu.

Multilingual E5 cung cấp biểu diễn văn bản đa ngôn ngữ và được chọn làm encoder cho tìm kiếm ngữ nghĩa [2]. FAISS đảm nhiệm lập chỉ mục và truy vấn vector [3]. Hai thành phần có chức năng khác nhau: encoder quyết định biểu diễn, còn chỉ mục quyết định cách tổ chức và tìm kiếm các vector đã tạo. Việc tạo lại chỉ mục sau khi bổ sung corpus không đồng nghĩa huấn luyện lại encoder.

BM25 và TF-IDF đại diện cho truy xuất từ vựng. RRF gộp các danh sách xếp hạng mà không cần coi điểm BM25 và cosine là cùng thang đo [4]. Những phương pháp này được sử dụng làm đối chứng. Đóng góp của đồ án nằm ở tổ chức dữ liệu hai miền, phối hợp truy xuất với điều kiện mã, ngày và tỉnh, cùng thiết kế kiểm tra đầu ra trong ngữ cảnh cụ thể của dự án; không phải phát minh lại BM25, E5 hoặc RRF.

BEIR nhấn mạnh nhu cầu so sánh nhiều họ phương pháp trên các tập dữ liệu khác nhau [5]. GS-QA, MapQA và nghiên cứu Tourism QA cho thấy bài toán địa lý hoặc du lịch có những loại đầu vào và đáp án rất khác nhau [6–8]. Các bộ này liên quan đến định hướng của đồ án, nhưng chưa được thực nghiệm trong sản phẩm hiện có. Vì vậy, kết quả trên corpus dự án và câu hỏi tự xây dựng không được ghi thành điểm benchmark của những bộ dữ liệu công khai đó.

## 1.3 Phương pháp và phạm vi nghiên cứu

### 1.3.1 Câu hỏi nghiên cứu

RQ1 xem xét mức độ khác nhau giữa tìm kiếm từ vựng, tìm kiếm ngữ nghĩa và kết hợp hạng khi câu hỏi chứa mã đơn vị, ngày snapshot, tên điểm đến hoặc từ khóa tỉnh. Giả thuyết làm việc là thông tin có tính định danh chính xác cần được xử lý khác với mô tả trải nghiệm; một phương pháp duy nhất khó tối ưu cho mọi nhóm câu hỏi.

RQ2 xem xét tác động của dữ liệu mới. Corpus mở rộng có thể bổ sung tài liệu cần thiết cho những câu hỏi trước đây không có đáp án, nhưng cũng có thể làm thay đổi thứ hạng của câu hỏi cũ. Thí nghiệm vì thế chạy cùng giao thức trên D0 và D1, đồng thời báo cáo riêng nhóm câu hỏi đã có trước mở rộng.

RQ3 xem xét hiệu quả của tổ hợp có ràng buộc. Biến thể đề xuất dùng phân miền, từ khóa tỉnh cũ và mới, điều kiện mã và ngày trước khi chọn kết quả từ các danh sách xếp hạng. Cần đánh giá thêm tỷ lệ từ chối khi ngày yêu cầu không có bằng chứng, vì xếp hạng được một tài liệu không đồng nghĩa tài liệu đó xác nhận ngày được hỏi.

RQ4 xác định mức độ đáp ứng kế hoạch triển khai. Một đồ án hoàn chỉnh phải đối chiếu các yêu cầu về dữ liệu, backend, giao diện, đánh giá và đóng gói với tệp code và báo cáo có thể kiểm tra. Các mục chưa có bằng chứng không được mặc nhiên xem là đã hoàn thành.

### 1.3.2 Mục tiêu và đóng góp

Mục tiêu kỹ thuật là xây dựng pipeline thu thập có provenance, biểu diễn các danh mục hành chính theo phiên bản, tạo nhánh tìm kiếm văn bản và tích hợp giao diện hỏi đáp có trích dẫn. Mục tiêu nghiên cứu là thiết lập các baseline, xây dựng dữ liệu mở rộng có thể kiểm kê, thử biến thể lai và trình bày kết quả kèm giới hạn. Hai nhóm mục tiêu liên hệ với nhau nhưng có tiêu chí đánh giá khác nhau: kiểm thử API đo hành vi phần mềm, còn chỉ số truy xuất đo khả năng tìm tài liệu theo nhãn đã biết.

Đóng góp thứ nhất là sản phẩm Tri Việt với đường tra mã theo KG và đường chọn mệnh đề bằng LLM. Đóng góp thứ hai là bộ dữ liệu nghiên cứu mở rộng giữ đồng thời snapshot, liên kết chuyển đổi, dòng đối chiếu có ngày và thông tin điểm tham quan. Đóng góp thứ ba là thực nghiệm bảy cấu hình trên hai phiên bản corpus, có ablation và phân tích theo loại câu hỏi. Những đóng góp này tạo thành kết quả sơ bộ có thể tái kiểm tra; chưa đủ để khẳng định một thuật toán mới có tính tổng quát toàn cầu.

### 1.3.3 Đối tượng sử dụng và phạm vi

Người dùng mục tiêu là người tra cứu địa phương và người tìm thông tin điểm đến trong phạm vi Việt Nam. Đầu vào hiện tại là văn bản tiếng Việt; giao diện chưa nhận ảnh, chưa nhận dạng địa điểm từ ảnh và chưa cung cấp tìm kiếm ảnh. Lịch sử hội thoại được lưu tại trình duyệt; hệ thống chưa có tài khoản người dùng hoặc đồng bộ hội thoại qua máy chủ.

Miền hành chính gồm danh mục và quan hệ chuyển đổi cũ, mới; miền du lịch gồm điểm đến vật thể và nội dung tham quan phù hợp. Chủ đề di sản phi vật thể đã được loại khỏi corpus hoạt động theo phạm vi điều chỉnh của dự án. Việc giữ thông tin tham quan một di tích không có nghĩa mở lại toàn bộ miền hỏi đáp di sản trước đây. Hồ sơ sáp nhập doanh nghiệp xuất hiện trong tài liệu mẫu nhưng không có bộ dữ liệu và luồng ứng dụng tương ứng trong sản phẩm hiện tại.

Về thời gian, dữ liệu nền có ba mốc 30/06/2025, 01/07/2025 và 24/10/2026. Lần quan sát bảng NSO ngày 30/10/2026 được giữ riêng. Các mốc này không tạo thành timeline liên tục. Về không gian, quan hệ thuộc tỉnh đã được xử lý; polygon, giao nhau, gần nhất và bán kính chưa có bộ thực thi được kiểm chứng. Về mô hình, cấu hình đã chạy sử dụng Qwen3-0.6B qua Transformers, không phải LLaMA-2 qua vLLM như phương án dự kiến trong PDF kế hoạch.

### 1.3.4 Phương pháp thực hiện

Nghiên cứu bắt đầu bằng kiểm kê thư mục code, cấu hình và artifacts. Sau đó, các trường dữ liệu được ánh xạ sang schema có cấu trúc; văn bản được tách đoạn để lập chỉ mục. Câu hỏi có mã được nhận diện trước bộ phân loại thống kê. Với các câu còn lại, router và quy tắc chọn KG, RAG hoặc kết hợp. Các mệnh đề chỉ được xuất khi vượt qua bước kiểm tra tương ứng với loại minh chứng.

Thực nghiệm truy xuất sử dụng cùng câu hỏi và cùng cách tính điểm trên D0 và D1. Tham số RRF và cấu hình ứng viên được cố định trước khi xem kết quả test. Tập câu hỏi silver được chia theo nhóm thực thể, còn 16 câu phát triển thủ công được báo cáo riêng. Việc chấm câu trả lời cuối bằng người đánh giá độc lập là một công việc tiếp theo, không được thay bằng tỷ lệ unit test đạt.

## 1.4 Thực nghiệm định hướng và kết quả ban đầu

Đối với lỗi mã 00008, kiểm thử hồi quy kiểm tra đồng thời miền, route, mã, tên đơn vị, tỉnh, mốc dữ liệu và nguồn KG. Các ca âm gồm mã không có trong dữ liệu, nhiều mã trong một câu, mã bưu chính, mã đặt phòng, số trong tên “Phường 12”, ngày không hợp lệ và bản ghi thay đổi giữa hai lần đọc. Mô hình sinh và retriever được giả lập để báo lỗi nếu bị gọi trong đường tra mã đơn giản. Cách kiểm thử này xác nhận được một thuộc tính kiến trúc cụ thể: kết quả tra mã không phụ thuộc việc LLM có đang sẵn sàng hay không.

Lần kiểm tra lại code trong đợt viết báo cáo đạt 353 unit test. Báo cáo HTTP đã lưu của bản sửa tra mã ghi 65/65 ca đạt, còn kiểm tra Chromium ghi 33/33. Hai bộ sau là bằng chứng lịch sử của D0; không được dùng để tuyên bố đã kiểm thử end-to-end bản D1. Chương 5 trình bày kết quả truy xuất mới, được chạy riêng trên D1.

Corpus tăng từ 31.949 tài liệu ở D0 lên 38.993 ở D1. D1 có 825 điểm du lịch được gắn tỉnh theo bộ lọc nguồn, phủ 34 tỉnh/thành trong dữ liệu. Số lượng này là phạm vi đã thu thập, không phải danh sách toàn bộ điểm du lịch Việt Nam. Trên bộ test silver của D1, biến thể lai đạt MRR@10 bằng 0,9297, trong khi E5 đạt 0,6181. Tuy nhiên, trên 16 câu thủ công, RRF thông thường đạt 0,8854 và cao hơn biến thể có ràng buộc 0,8125. Phản chứng này là cơ sở để tiếp tục đánh giá thay vì chọn phương pháp chỉ theo điểm tổng thuận lợi.

Mục tiêu Accuracy/F1 tiệm cận 90–98% trong kế hoạch được hiểu là mục tiêu cần định nghĩa phép đo, không phải kết quả đã có của toàn hệ thống. Accuracy 1,0 trên 17 ca KG hoặc tỷ lệ HTTP 65/65 không chứng minh độ đúng 100% của nguồn dữ liệu và mọi câu trả lời. Các chỉ số được giữ đúng đơn vị đo xuyên suốt báo cáo.

## 1.5 Kết luận

Chương 1 xác lập bài toán kết hợp hai miền tri thức, yêu cầu bảo toàn điều kiện tra cứu và nhu cầu phân biệt các loại bằng chứng. Hệ thống có kết quả phần mềm và thực nghiệm ban đầu, đồng thời còn khoảng trống về benchmark công khai, hình học địa lý và đánh giá ngữ nghĩa độc lập. Các chương tiếp theo lần lượt trình bày cơ sở lý thuyết, dữ liệu và phương pháp, thiết kế triển khai, kết quả thực nghiệm và tổng kết đóng góp. Mỗi chương giữ cấu trúc giới thiệu, công trình liên quan, phương pháp hoặc dữ liệu, thực nghiệm và kết luận để có thể đối chiếu mục tiêu với bằng chứng ngay trong từng chủ đề.
