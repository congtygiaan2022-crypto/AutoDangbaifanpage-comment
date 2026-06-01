
import json
import unicodedata

def normalize_string(s):
    if not s:
        return ""
    return unicodedata.normalize('NFC', s).strip()

def update_folders():
    json_path = r"h:\Tool_tucode\AutoDangbaifanpage+comment\database.json"
    prefix_to_replace = "H:/4kdown/"
    new_prefix = r"C:\Users\congt\Documents\Antigravity_folder\downloads\\"
    
    # Raw mapping data from user
    raw_mapping = """
1 Phút Khoa Học	H:/4kdown/1 Phút Khoa Học
24h Giải Trí	H:/4kdown/24h Giải Trí Shorts
2B News	H:/4kdown/return to childhood
2B Trending	H:/4kdown/YAN News Shorts
1hay Tv	H:/4kdown/Ibiz Shorts
Bác Vladimir	H:/4kdown/Bác Vladimir Shorts
Ba Vạn Dặm Dưới Đáy Biển	H:/4kdown/Ba Vạn Dặm Dưới Đáy Biển Shorts
Bóng Đá Mỗi Ngày	H:/4kdown/Football Global Shorts
Chiêm Tinh TV	H:/4kdown/Chiêm Tinh TV Shorts
Cô Tấm Douyin	H:/4kdown/Gái Xinh Shorts
Cuộc Sống Mỗi Ngày	H:/4kdown/Pháp Luật Xã Hội Shorts
Drama Showbiz	H:/4kdown/KEN TV ENTERTAINMENT Shorts
Đàm Đạo Gaming	H:/4kdown/Đàm Đạo Gaming Shorts
Đỡ phải hóng 24/7	H:/4kdown/KENH14 NEWS Shorts
Fantastic Trending	H:/4kdown/FANTASTIC TREND Shorts
Fox Review	H:/4kdown/Fox Review Shorts
Gams - AI trending	H:/4kdown/Hasidama Shorts
Gams - Cuộc Sống Mỗi Ngày	H:/4kdown/Pháp Luật Xã Hội Shorts
Gams - Giải Trí	H:/4kdown/VGT TV - Giải Trí Shorts
Gams - Sao Việt	H:/4kdown/VGT TV - Sao Việt Shorts
Gams Discovery	H:/4kdown/Phi Đi Khám Phá Shorts
Gams Kids	H:/4kdown/Hóm Boy Shorts
Gams Music	H:/4kdown/AT Music Shorts
Gams Review Đời Sống	H:/4kdown/Khủng Long Review Shorts
Híp Hài Hước	H:/4kdown/Dũng CM Shorts
Job30s News	H:/4kdown/Job30s News Shorts
Lãnh Địa Samsung	H:/4kdown/Lãnh Địa Sam Sung Shorts
Mẹo nhỏ thú vị	H:/4kdown/Fun little tip Shorts
Mỗi Ngày Một Chút	H:/4kdown/Mỗi Ngày Một Chút Shorts
Ngọn Đèn Tri Thức	H:/4kdown/Trí Tuệ Cổ Nhân Shorts
ONDA News	
Ống Kính Hậu Trường	H:/4kdown/Ống Kính Hậu Trường Shorts
Sử Đại Phát Minh	H:/4kdown/Sử Đại Phát Minh Shorts
T8 Trending	H:/4kdown/TB Trends Shorts
Tạp Hoá Người Lười	H:/4kdown/Tạp Hoá Người Lười Shorts
Tee Cloudy	H:/4kdown/Tee Cloudy Shorts
TIỆN ÍCH GIA ĐÌNH	H:/4kdown/Tiện Ích Gia Đình Shorts
Tin Này Trending	H:/4kdown/YAN News Shorts
TM98	H:/4kdown/TheManh98 Gamer Shorts
TM98 Trending	H:/4kdown/Themanh98 Trending Shorts
Tiếng Cười Kiến Thức	H:/4kdown/Tiếng Cười Kiến Thức Shorts
Xóm Nhiều Chuyện	H:/4kdown/Mỹ Nữ Lầy Lội Shorts
Yêu Lu Channel	H:/4kdown/YÊU LU Shorts
    """
    
    mapping_dict = {}
    for line in raw_mapping.strip().split('\n'):
        if not line.strip(): continue
        parts = line.split('\t')
        name = normalize_string(parts[0])
        path = parts[1].strip() if len(parts) > 1 else ""
        
        if path:
            processed_path = path.replace(prefix_to_replace, new_prefix).replace('/', '\\')
            mapping_dict[name.lower()] = processed_path
            
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        fanpages = data.get('fanpages', [])
        updated_count = 0
        
        for page in fanpages:
            name = normalize_string(page.get('name', ''))
            key = name.lower()
            if key in mapping_dict:
                new_path = mapping_dict[key]
                # The user said "Gán các thư mục theo folder tương ứng", 
                # implying replacing the existing folder list or setting it.
                # Usually these tools expect a list of strings.
                page['folders'] = [new_path]
                updated_count += 1
                
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        print(f"Updated folders for {updated_count} fanpages.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_folders()
