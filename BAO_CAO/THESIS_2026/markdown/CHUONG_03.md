# CHƯƠNG 3 DỮ LIỆU VÀ PHƯƠNG PHÁP NGHIÊN CỨU

## 3.1 Giới thiệu

Chương 3 mô tả cách xây dựng dữ liệu, thiết kế bộ câu hỏi và xác lập các cấu hình so sánh. Chương này trả lời hai câu hỏi về provenance: mỗi bản ghi bắt nguồn từ đâu và có thể hỗ trợ điều kiện nào. Đồng thời, chương phân biệt dữ liệu có sẵn trong dự án với phần mới thu thập để tránh coi việc tải lại một bảng như hàng nghìn sự kiện hành chính mới.

Ký hiệu D0 chỉ corpus hoạt động trước đợt mở rộng, có 31.949 tài liệu. D1 là release nghiên cứu riêng có 38.993 tài liệu. D1 giữ nguyên toàn bộ ID và nội dung D0, thêm đoạn hành chính có nguồn, điểm du lịch mới và các dòng quan sát bảng NSO được gắn ngày riêng. Hai bộ dùng cùng một giao thức truy xuất trong thí nghiệm; ứng dụng local không tự đổi sang D1 sau khi script nghiên cứu hoàn tất.

## 3.2 Công trình và nguồn dữ liệu liên quan

Nguồn danh mục cộng đồng vietnam-provinces phiên bản 2026.9.0 cung cấp dữ liệu nền và liên kết chuyển đổi [12]. Đây là dữ liệu có sẵn được tái sử dụng, không phải kết quả nhóm tự điều tra thực địa. Bộ nền cần được giữ phiên bản và đối chiếu nguồn chính thức khi có thể. Việc thư viện có quan hệ chuyển đổi không tự chứng minh đầy đủ hiệu lực pháp lý của từng phần địa bàn.

Bảng đối chiếu NSO cung cấp tên, mã, tỉnh, văn bản tham chiếu và ghi chú theo các cột thời gian [13]. Nguồn Chính phủ gồm bài tổng hợp và liên kết toàn văn nghị quyết, phục vụ thu thập các đoạn nói về đơn vị cũ và đơn vị hình thành sau sắp xếp [14]. Cơ sở dữ liệu ngành Du lịch cung cấp danh sách theo tỉnh và trang chi tiết điểm đến [15]. Nguồn có thẩm quyền được ưu tiên, nhưng trường còn thiếu hoặc mốc thời gian chưa xác định vẫn phải được biểu diễn là chưa biết.

Các hướng nghiên cứu hỏi đáp địa lý và du lịch [6–8] gợi ý rằng bộ dữ liệu cần không chỉ có văn bản, mà còn có điều kiện và kiểu đáp án. Đối với phạm vi hiện tại, điều kiện thực thi được là mã, tỉnh và snapshot có trong nguồn. Dữ liệu hình học cần cho khoảng cách và vùng không gian là một lớp khác, chưa có đầy đủ trong release này.

## 3.3 Phương pháp và dữ liệu

### 3.3.1 Hợp đồng bản ghi

Mỗi bản ghi có record_id, record_type, domain, source_name, source_url và đối tượng data. Các loại chính gồm administrative_snapshot, administrative_conversion, administrative_reference, administrative_source_document, administrative_legal_passage và tourism_place. Tài liệu RAG giữ ID liên kết với bản ghi, tiêu đề, văn bản, miền và nguồn. SQLite metadata liên kết chunk với doc_id để có thể đi từ kết quả vector về bản ghi nguồn.

Ở snapshot, các trường cần thiết là snapshot, snapshot_date, level, code, name, province_code, province_name và các trường hiệu lực khi được ghi nhận. Bản ghi lịch sử phù hợp có thêm district_code hoặc district_name. Ở chuyển đổi, dữ liệu giữ old_code, old_name, new_code, new_name và is_partial. Không dùng tên hiện tại để viết đè tên của baseline năm 2025.

Ở điểm du lịch, tên, địa chỉ và mô tả được giữ từ nguồn. province_code và province_name được gắn theo bộ lọc danh sách chính thức của nguồn du lịch; trường province_mapping_basis mô tả căn cứ ánh xạ. Điều này giúp truy xuất bằng tỉnh mới khi nguồn nhóm các mã tỉnh cũ, nhưng không chứng minh từng địa chỉ đã được quy đổi đến xã mới. address_time_scope ghi rõ giới hạn đó.

Ở đoạn hành chính, description là văn bản nguồn được giữ nguyên. Thông tin section và URL phục vụ đặt đoạn vào ngữ cảnh. Khi hai đoạn chỉ khác số thứ tự hoặc dấu câu, một bản được giữ cùng danh sách URL bổ sung. Dữ liệu không tự tạo hiệu lực từ ngày thu thập; trường chưa xác định có thể là null. Cờ partial_transfer_mentioned chỉ ghi nhận cụm từ về chuyển một phần, không thay thế quá trình suy luận hay thẩm định toàn bộ sự kiện.

### 3.3.2 Quy tắc thời gian

Có bốn loại thời điểm cần phân biệt: ngày xuất bản, ngày thu thập, ngày quan sát danh mục và khoảng hiệu lực pháp lý. Một trang được tải ngày 30/10/2026 vẫn có thể mô tả sự kiện năm 2025. Ngược lại, cột đối chiếu 31/10/2025 không phải danh mục trước tháng 7/2025. Các trường này được lưu riêng để tránh suy diễn sai thứ tự trước và sau sắp xếp.

Ba snapshot nền là legacy ngày 30/06/2025, reorganized2025 ngày 01/07/2025 và current ngày 24/10/2026. Tên current chỉ có nghĩa đây là bản được phần mềm chọn khi không yêu cầu ngày; nó không có cơ chế tự tiến theo đồng hồ. Bảng NSO được quan sát lại ngày 30/10/2026 nhưng vẫn là các dòng reference, không tự tạo một khoảng hiệu lực mới cho mọi node.

Khi có snapshotDate, câu hỏi theo ngày chỉ được xác nhận tại ngày tương ứng trong dữ liệu. Khoảng hiệu lực hai đầu có thể được kiểm tra nếu nguồn đủ căn cứ. Không nội suy mốc còn thiếu từ hai snapshot. Nếu người dùng hỏi “hôm nay”, “trước ngày” hoặc một khoảng năm chưa được bộ thực thi hỗ trợ, phản hồi phải nêu giới hạn thay vì bỏ qua điều kiện rồi trả lời như câu không có thời gian.

### 3.3.3 Thu thập và lưu bằng chứng

PublicCrawler lưu HTML cache, URL, trạng thái HTTP hoặc cached, số byte, SHA256 và thời điểm xử lý. Robots được kiểm tra trước khi truy cập; yêu cầu tới cùng host được giãn cách. Các trang bảng có phân trang được đi qua bằng công cụ trình duyệt để lưu DOM của từng trang hiển thị. Bảng NSO được kiểm tra đủ 3.321 mã không trùng trước khi đưa vào bước chuẩn hóa.

Đợt nghiên cứu thu từ một bài tổng hợp và 33 trang nghị quyết liên kết của Chính phủ. Có 6.108 đoạn sau bước chọn đoạn theo nội dung sắp xếp; khử trùng các biến thể số thứ tự và dấu câu còn 3.351 đoạn. Những con số này là số đoạn văn, không phải số nghị quyết, số tỉnh hoặc số sự kiện sáp nhập riêng biệt.

Ở nhánh du lịch, script đi theo tỉnh và các phân trang công khai của điểm đến, khu du lịch và vui chơi giải trí. URL đã có trong D0 được bỏ qua để ưu tiên bản ghi mới. Mục tiêu thu thập là tối đa 20 bản ghi mới mỗi tỉnh trong lượt chạy, không phải cam kết mọi tỉnh đều có đúng 20 điểm hoặc đã được thu thập toàn bộ. Kết quả có thêm dữ liệu ở 27 tỉnh; tổng corpus vẫn phủ 34 tỉnh/thành nhờ các bản đã có.

### 3.3.4 Làm sạch và kiểm soát chất lượng

Chuẩn hóa Unicode và khoảng trắng giúp thống nhất chuỗi mà vẫn giữ nội dung nguồn. Bộ lọc chủ đề loại các câu về di sản phi vật thể khỏi phần mô tả du lịch, đồng thời giữ điểm tham quan vật thể phù hợp. Trong các điểm mới, audit ghi nhận 38 câu nguồn được loại. Không bỏ dấu toàn văn để quyết định xóa nội dung vì có thể nhầm tên địa lý với tên loại hình nghệ thuật.

Khử trùng được thực hiện trên khóa phục vụ so sánh, không ghi đè văn bản bằng chuỗi đã bỏ dấu câu. Các URL bổ sung được giữ để truy nguyên. Các bản raw còn cho phép đọc lại câu trước khi lọc. Quy trình này khác với “tăng số lượng dữ liệu” bằng việc giữ lặp nhiều bản gần giống nhau mà không báo cáo tỷ lệ trùng.

Kiểm tra bảo toàn so sánh ID và nội dung của từng bản D0 với D1. Checksum của active corpus được đối chiếu với giá trị trước thu thập. Kết quả cho thấy D0 không bị thay trong đợt nghiên cứu. Các archives không được sửa lại. Một sai sót vệ sinh archive không hoạt động của giai đoạn trước đã được ghi trong hồ sơ bảo trì; không sử dụng các archive đó làm đầu vào train hoặc truy xuất của D1.

### 3.3.5 Xây dựng câu hỏi và nhãn

Tập silver có 263 câu được sinh từ mã, ngày, tên điểm đến, đoạn sắp xếp và từ khóa tỉnh. Mỗi câu có ID, danh sách relevant_doc_ids, nhóm thực thể, split, loại câu, nguồn câu hỏi và trạng thái nhãn. Nhãn được suy từ nguồn để hỗ trợ phát triển, chưa được người độc lập xác nhận toàn bộ. Một câu danh sách tỉnh có thể có nhiều tài liệu dương; một câu ngày không có snapshot có danh sách dương rỗng.

Nhóm thực thể được băm SHA256 để chia dev/test theo quy tắc cố định. Các snapshot cùng mã ở cùng split. Tập dev có 52 câu; test có 211 câu, gồm 188 câu có nhãn dương và 23 câu không có snapshot phù hợp. Cách chia theo nhóm giảm một dạng rò rỉ thực thể, nhưng không loại được tương đồng giữa các khuôn câu tự sinh.

Bộ 16 câu phát triển thủ công trước đó được giữ riêng để làm kiểm tra chéo với kết quả silver. Những câu này đã có vai trò phát triển từ trước và không được gọi là test kín. Phiếu annotation_review.csv chứa câu hỏi, nguồn, đoạn hỗ trợ và chỗ người duyệt ghi nhận xét. Mọi chỉ số hiện tại được đọc như known-positive metrics vì có thể còn tài liệu mới tương đương chưa được đánh dấu dương.

### 3.3.6 Các cấu hình thực nghiệm

Cấu hình M1 dùng TF-IDF. M2 dùng BM25. M3 dùng E5. M4 gộp BM25 và E5 bằng RRF. M5 thêm lọc miền vào M4. M6 thêm điều kiện tỉnh và ánh xạ tên tỉnh cũ–mới vào M5. M7 thêm đường tra khóa hành chính theo mã và ngày vào M6. Cấu hình cuối là tổ hợp đề xuất cho bài toán, có thể trả tập rỗng khi không có snapshot đáp ứng điều kiện.

Mỗi nhánh xếp hạng nhận cùng corpus chunk của phiên bản đang xét. Candidate limit là 200 chunk; kết quả được gộp theo tài liệu và đánh giá top 10. Bộ router D0 được đóng băng cho cả hai corpus để hạn chế việc gộp hiệu ứng thêm dữ liệu với thay mô hình phân miền. Router D1 vẫn được train lại, nhưng có báo cáo riêng và không thay router trong thí nghiệm truy xuất này.

Cấu hình thời gian đọc điều kiện từ câu hỏi, dựng kế hoạch và tra metadata bản ghi. Nó không đọc relevant_doc_ids để chọn đáp án. Các câu về bảng đối chiếu hoặc ghi chú chuyển đổi được giữ ở nhánh văn bản thay vì mặc nhiên coi mọi mã xuất hiện trong câu là yêu cầu lấy tên snapshot. Các ca nhiều mã hoặc loại mã khác cần làm rõ được xử lý theo chính sách tương ứng.

## 3.4 Thực nghiệm kiểm kê dữ liệu

Bảng 3.1 Thành phần corpus theo loại bản ghi

| Loại bản ghi | D0 | D1 |
|---|---|---|
| Snapshot hành chính | 17520 | 17520 |
| Liên kết chuyển đổi | 10618 | 10618 |
| Hồ sơ thuộc tính văn bản | 37 | 37 |
| Dòng quan sát đối chiếu | 3321 | 6642 |
| Đoạn hành chính riêng biệt | 0 | 3351 |
| Điểm du lịch | 453 | 825 |
| Tổng tài liệu | 31949 | 38993 |

D1 có 38.168 tài liệu hành chính và 825 tài liệu du lịch. 6.642 reference bao gồm hai lần quan sát 3.321 dòng; chúng không đại diện 6.642 đơn vị hành chính riêng biệt. Tương tự, 6.642 node Ward trong KG là tổng các phiên bản, không có nghĩa Việt Nam có 6.642 đơn vị cấp xã hiện hành trong danh mục mà ứng dụng chọn.

Bảng đối chiếu quan sát lại không có thay đổi ở các trường tên, tỉnh, văn bản tham chiếu và ghi chú được script so sánh với lần trước. Giá trị của lần thu thập mới ở đây là bằng chứng quan sát có thời gian và khả năng kiểm tra lại nguồn. Kết luận “không có thay đổi ở các trường được so sánh” cũng không thay thế một cuộc thẩm định pháp lý đầy đủ về mọi đơn vị và mọi văn bản.

Dữ liệu du lịch phân bố không đều. Một số tỉnh chỉ có hai điểm trong corpus, trong khi các địa phương khác có hơn ba mươi. Do đó, một phản hồi không tìm được điểm không chứng minh địa phương không có điểm du lịch. Khi đánh giá tìm theo tỉnh, cần nêu đây là danh sách trong dữ liệu đang có và theo dõi độ phủ từng tỉnh riêng.

Bảng CSV administrative_crosswalk.csv có 10.618 liên kết chuyển đổi nền với mã, tên, tỉnh cũ, huyện cũ khi có, đơn vị mới và cờ chuyển một phần. Đây là cách xuất dữ liệu đã có để đối chiếu, không được tính lần nữa là 10.618 sự kiện mới do đợt crawl phát hiện. Khả năng gắn từng cạnh với một khoản cụ thể trong văn bản pháp lý vẫn là công việc cần kiểm chứng tiếp.

Đợt xây chỉ mục cuối tạo 41.280 vector 768 chiều. Những đoạn có nội dung và cấu hình encoder không đổi được tái sử dụng từ chỉ mục trước; đoạn mới được mã hóa lại. Dữ liệu đóng băng trung gian được giữ để có thể giải thích quá trình tái sử dụng. Cấu hình cuối không đánh dấu việc tạo embedding là fine-tune mô hình.

## 3.5 Kết luận

Dữ liệu mở rộng có thể truy nguyên và có phân biệt giữa bản ghi mới, quan sát mới và biến thể trùng. Thiết kế câu hỏi cho phép so sánh trên dữ liệu cũ và mới, nhưng chất lượng nhãn còn ở mức phát triển. Những giới hạn về timeline, độ phủ du lịch và pháp lý từng cạnh cần được duy trì trong báo cáo kết quả. Chương 4 chuyển từ hợp đồng dữ liệu sang cách thực hiện hệ thống và cơ chế kiểm tra các điều kiện này.
