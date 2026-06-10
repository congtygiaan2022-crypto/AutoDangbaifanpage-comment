import os
import json
import logging
from db_helper import db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migrate")

def migrate_fb_logs(file_path="logs.json"):
    if not os.path.exists(file_path):
        logger.warning(f"File {file_path} not found. Skipping fb_posts migration.")
        return

    logger.info(f"Migrating {file_path}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        params_list = []
        # format of logs.json is dict: {"link": [{"timestamp": "...", "video": "...", "status": "...", "link": "post_link"}]}
        if isinstance(data, dict):
            for link, logs in data.items():
                if isinstance(logs, list):
                    for log in logs:
                        timestamp = log.get("timestamp", "")
                        video = log.get("video", "")
                        status = log.get("status", "")
                        post_link = log.get("link", "") # The individual post link
                        
                        params_list.append((timestamp, video, status, link))
        
        if params_list:
            query = "INSERT OR IGNORE INTO fb_posts (timestamp, video, status, link) VALUES (?, ?, ?, ?)"
            inserted = db.executemany(query, params_list)
            logger.info(f"Successfully inserted {inserted} records into fb_posts from {len(params_list)} total items.")
        else:
            logger.info("No records to migrate for fb_posts.")
            
    except Exception as e:
        logger.error(f"Error migrating {file_path}: {e}")

def migrate_comment_history(file_path="comment_history.json"):
    if not os.path.exists(file_path):
        logger.warning(f"File {file_path} not found. Skipping comment_history migration.")
        return

    logger.info(f"Migrating {file_path}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        params_list = []
        if isinstance(data, dict):
            for page_link, logs in data.items():
                if isinstance(logs, list):
                    for log in logs:
                        timestamp = log.get("timestamp", "")
                        video = log.get("video", "")
                        post_link = log.get("post_link", "")
                        
                        params_list.append((page_link, video, post_link, timestamp))
        
        if params_list:
            query = "INSERT OR IGNORE INTO comment_history (page_link, video, post_link, timestamp) VALUES (?, ?, ?, ?)"
            inserted = db.executemany(query, params_list)
            logger.info(f"Successfully inserted {inserted} records into comment_history from {len(params_list)} total items.")
        else:
            logger.info("No records to migrate for comment_history.")
            
    except Exception as e:
        logger.error(f"Error migrating {file_path}: {e}")

def migrate_youtube(file_path="youtube.json"):
    if not os.path.exists(file_path):
        logger.warning(f"File {file_path} not found. Skipping youtube_downloads migration.")
        return
        
    logger.info(f"Migrating {file_path}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        params_list = []
        if isinstance(data, list):
            for item in data:
                timestamp = item.get("timestamp", "")
                title = item.get("title", "")
                url = item.get("url", "")
                file_path = item.get("file_path", "")
                status = item.get("status", "")
                params_list.append((timestamp, title, url, file_path, status))
        
        if params_list:
            query = "INSERT OR IGNORE INTO youtube_downloads (timestamp, title, url, file_path, status) VALUES (?, ?, ?, ?, ?)"
            inserted = db.executemany(query, params_list)
            logger.info(f"Successfully inserted {inserted} records into youtube_downloads.")
            
    except Exception as e:
        logger.error(f"Error migrating youtube.json: {e}")

def migrate_tiktok(file_path="tiktok.json"):
    if not os.path.exists(file_path):
        logger.warning(f"File {file_path} not found. Skipping tiktok_downloads migration.")
        return
        
    logger.info(f"Migrating {file_path}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        params_list = []
        if isinstance(data, list):
            for item in data:
                timestamp = item.get("timestamp", "")
                title = item.get("title", "")
                url = item.get("url", "")
                file_path = item.get("file_path", "")
                status = item.get("status", "")
                params_list.append((timestamp, title, url, file_path, status))
        
        if params_list:
            query = "INSERT OR IGNORE INTO tiktok_downloads (timestamp, title, url, file_path, status) VALUES (?, ?, ?, ?, ?)"
            inserted = db.executemany(query, params_list)
            logger.info(f"Successfully inserted {inserted} records into tiktok_downloads.")
            
    except Exception as e:
        logger.error(f"Error migrating tiktok.json: {e}")

if __name__ == "__main__":
    from init_db import init_db
    init_db()  # Ensure database and tables exist
    
    migrate_fb_logs()
    migrate_comment_history()
    migrate_youtube()
    migrate_tiktok()
    
    logger.info("All possible migrations completed. Check system.db for data.")
