import json
import os

target_file = r"h:\Tool_tucode\AutoDangbaifanpage+comment\database.json"

new_fanpages = [
    {
        "stt": 1,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=934554456403623",
        "name": "1 Phút Khoa Học",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 2,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=876758202185345",
        "name": "Sử Đại Phát Minh",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 3,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=892104790652468",
        "name": "Chiêm Tinh TV",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 4,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=790617277479063",
        "name": "Job30s News",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 5,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=916112198244142",
        "name": "Tiếng Cười Kiến Thức",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 6,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=791280707411055",
        "name": "Ba Vạn Dặm Dưới Đáy Biển",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 7,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=813632545175301",
        "name": "Tạp Hoá Người Lười",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 8,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=860301350498374",
        "name": "Gams Review Đời Sống",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 9,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=805484859321324",
        "name": "Gams Music",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 10,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=399102339950231",
        "name": "2B Trending",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 11,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=875426935647329",
        "name": "24h Giải Trí",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 12,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=977181332144438",
        "name": "TM98 Trending",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 13,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=781578235047131",
        "name": "TM98",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 14,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=255354824325945",
        "name": "Mỗi Ngày Một Chút",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 15,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=755421237652298",
        "name": "Tee Cloudy",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 16,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=766794183178574",
        "name": "Mẹo nhỏ thú vị",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 17,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=683122174892165",
        "name": "Bác Vladimir",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 18,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=639952552542150",
        "name": "Fantastic Trending",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 19,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=593186283887196",
        "name": "Gams - AI trending",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 20,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=243738568828870",
        "name": "Đỡ phải hóng 24/7",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 21,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=364288856776144",
        "name": "Ngọn Đèn Tri Thức",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 22,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=439411339247687",
        "name": "Gams Kids",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 23,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=429438740246703",
        "name": "Fox Review",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 24,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=432464039939346",
        "name": "Xóm Nhiều Chuyện",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 25,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=336389219568420",
        "name": "Ống Kính Hậu Trường",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 26,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=424660574056022",
        "name": "Cuộc Sống Mỗi Ngày",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 27,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=375058405699413",
        "name": "1hay Tv",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 28,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=415536791637829",
        "name": "Drama Showbiz",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 29,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=401398659721765",
        "name": "Gams - Giải Trí",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 30,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=404671369392617",
        "name": "Gams - Sao Việt",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 31,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=353068807899001",
        "name": "Gams - Cuộc Sống Mỗi Ngày",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 32,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=421351801057588",
        "name": "T8 Trending",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 33,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=335663316308017",
        "name": "2B News",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 34,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=372062852659950",
        "name": "Cô Tấm Douyin",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 35,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=107022318734578",
        "name": "Híp Hài Hước",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 36,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=267848649745115",
        "name": "Tin Này Trending",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 37,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=212268081978980",
        "name": "Gams Discovery",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 38,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=258242084036458",
        "name": "Yêu Lu Channel",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 39,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=230962290109230",
        "name": "Bóng Đá Mỗi Ngày",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 40,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=272065429314390",
        "name": "Lãnh Địa Samsung",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 41,
        "link": "https://business.facebook.com/latest/bulk_upload_composer?asset_id=243011832229391",
        "name": "TIỆN ÍCH GIA ĐÌNH",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    },
    {
        "stt": 42,
        "link": "",
        "name": "",
        "folders": [],
        "min_videos": 1,
        "max_videos": 10
    }
]

try:
    with open(target_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception:
    data = {}

data['fanpages'] = new_fanpages

with open(target_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("Database updated successfully.")
