import json
import os
from db_helper import db

class Database:
    def __init__(self, file_path="database.json"):
        self.file_path = file_path
        self.data = self.load()


    def save_logs(self):
        pass # Deprecated in favor of db_helper


    def load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # MIGRATION: Migration logic for logs removed, now handled by migrate_all.py

                
                # ... existing migrations ...
                if 'comment_template' not in data:
                    data['comment_template'] = ""
                if 'auto_delete_videos' not in data:
                    data['auto_delete_videos'] = False
                if 'fanpages' in data:
                    for i, page in enumerate(data['fanpages']):
                        if 'min_videos' not in page:
                            page['min_videos'] = 1
                        if 'max_videos' not in page:
                            page['max_videos'] = 10
                        if 'name' not in page:
                            page['name'] = ""
                        # Ensure STT is present and correct
                        page['stt'] = i + 1
                # Scheduling settings
                if 'loop_mode' not in data:
                    data['loop_mode'] = 'once'
                if 'loop_count' not in data:
                    data['loop_count'] = 1
                if 'rest_min' not in data:
                    data['rest_min'] = 30
                if 'rest_max' not in data:
                    data['rest_max'] = 60
                if 'time_start' not in data:
                    data['time_start'] = '00:00'
                if 'time_end' not in data:
                    data['time_end'] = '23:59'
                # Theme setting
                if 'theme' not in data:
                    data['theme'] = 'dark'
                
                if 'run_mode' not in data:
                    data['run_mode'] = 'post_and_comment'
                
                return data

        return {"fanpages": [], "comment_template": "", "auto_delete_videos": False, 
                "loop_mode": "once", "loop_count": 1, "rest_min": 30, "rest_max": 60,
                "time_start": "00:00", "time_end": "23:59", "theme": "dark", "run_mode": "post_and_comment"}

    def reload(self):
        """ Reload all data from disk to ensure we have the latest config """
        self.data = self.load()
        return self.data


    def save(self):
        # Update STT before saving to ensure sequence is correct
        if 'fanpages' in self.data:
            for i, page in enumerate(self.data['fanpages']):
                page['stt'] = i + 1
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def set_comment_template(self, text):
        self.data['comment_template'] = text
        self.save()

    def get_comment_template(self):
        return self.data.get('comment_template', "")

    def set_auto_delete_videos(self, enabled):
        self.data['auto_delete_videos'] = enabled
        self.save()

    def get_auto_delete_videos(self):
        return self.data.get('auto_delete_videos', False)

    def get_scheduling_config(self):
        return {
            'loop_mode': self.data.get('loop_mode', 'once'),
            'loop_count': self.data.get('loop_count', 1),
            'rest_min': self.data.get('rest_min', 30),
            'rest_max': self.data.get('rest_max', 60),
            'time_start': self.data.get('time_start', '00:00'),
            'time_end': self.data.get('time_end', '23:59')
        }

    def set_scheduling_config(self, loop_mode, loop_count, rest_min, rest_max, time_start, time_end):
        self.data['loop_mode'] = loop_mode
        self.data['loop_count'] = loop_count
        self.data['rest_min'] = rest_min
        self.data['rest_max'] = rest_max
        self.data['time_start'] = time_start
        self.data['time_end'] = time_end
        self.save()

    def get_theme(self):
        return self.data.get('theme', 'dark')

    def set_theme(self, theme):
        self.data['theme'] = theme
        self.save()

    def get_run_mode(self):
        return self.data.get('run_mode', 'post_and_comment')

    def set_run_mode(self, mode):
        self.data['run_mode'] = mode
        self.save()

    def add_fanpage(self, link):
        # No 'logs' field needed anymore
        new_stt = len(self.data['fanpages']) + 1
        self.data['fanpages'].append({
            "stt": new_stt,
            "link": link, 
            "name": "", 
            "folders": [], 
            "min_videos": 1, 
            "max_videos": 10
        })
        self.save()

    def update_fanpage_name(self, index, name):
        if 0 <= index < len(self.data['fanpages']):
            self.data['fanpages'][index]['name'] = name
            self.save()

    def update_video_limits(self, page_index, min_videos, max_videos):
        if 0 <= page_index < len(self.data['fanpages']):
            self.data['fanpages'][page_index]['min_videos'] = min_videos
            self.data['fanpages'][page_index]['max_videos'] = max_videos
            self.save()

    def add_log(self, page_index, video_name, status, post_link=""):
        if 0 <= page_index < len(self.data['fanpages']):
            link = self.data['fanpages'][page_index]['link']
            
            db.add_fb_post_log(timestamp, video_name, status, link)

    def get_logs(self, link):
        return db.get_fb_logs(link)

    def remove_fanpage(self, index):
        if 0 <= index < len(self.data['fanpages']):
            self.data['fanpages'].pop(index)
            self.save()

    def add_folder(self, page_index, folder_path):
        if 0 <= page_index < len(self.data['fanpages']):
            if folder_path not in self.data['fanpages'][page_index]['folders']:
                self.data['fanpages'][page_index]['folders'].append(folder_path)
                self.save()

    def remove_folder(self, page_index, folder_index):
        if 0 <= page_index < len(self.data['fanpages']):
            if 0 <= folder_index < len(self.data['fanpages'][page_index]['folders']):
                self.data['fanpages'][page_index]['folders'].pop(folder_index)
                self.save()

    def update_link(self, index, new_link):
        if 0 <= index < len(self.data['fanpages']):
            self.data['fanpages'][index]['link'] = new_link
            self.save()

    def clear_all(self):
        self.data['fanpages'] = []
        self.save()

    def get_fanpages(self):
        return self.data['fanpages']

    # --- Comment History (New Feature) ---
    def load_comment_history(self):
        pass # Deprecated in favor of db_helper

    def save_comment_history(self):
        pass # Deprecated in favor of db_helper

    def add_comment_history(self, page_link, video_name, post_link):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.add_comment_history(page_link, video_name, post_link, timestamp)

    def has_commented(self, page_link, video_name):
        return db.has_commented(page_link, video_name)

    def get_comment_history(self, page_link):
        return db.get_comment_history(page_link)
    def select_video(self, page_index, folders, min_videos, max_videos):
        if not folders: return None
        
        # Check daily limit
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        page_link = self.data['fanpages'][page_index]['link']
        today_success = db.get_daily_success_count(page_link, today)
        if today_success >= int(max_videos):
            return None # Met daily limit

        
        # Find available videos
        valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        all_videos = []
        for folder in folders:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(valid_extensions):
                        full_path = os.path.join(folder, f)
                        all_videos.append(full_path)
        
        if not all_videos: return None
        
        # Pick random
        import random
        return random.choice(all_videos)

    def select_video_for_comment(self, page_index, folders, skip_existing=True):
        if not folders: return None
        
        page_link = self.data['fanpages'][page_index]['link']
        valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        all_videos = []
        
        for folder in folders:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(valid_extensions):
                        full_path = os.path.join(folder, f)
                        
                        # Filter if skip enabled
                        if skip_existing:
                            if self.has_commented(page_link, f):
                                continue
                        
                        all_videos.append(full_path)
        
        if not all_videos: return None
        
        # Pick random valid video
        import random
        return random.choice(all_videos)
