
import json
import os

def standardize_paths():
    path = r"h:\Tool_tucode\AutoDangbaifanpage+comment\database.json"
    target_prefix = r"C:\Users\congt\Documents\Antigravity_folder\downloads"
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    updated = 0
    for page in data.get('fanpages', []):
        folders = page.get('folders', [])
        new_folders = []
        for folder in folders:
            # Clean up the folder string
            f = folder.strip()
            # Remove leading comma if present (from my previous buggy script)
            if f.startswith(','):
                f = f[1:].strip()
            
            # Normalize path separators to backslashes
            f = f.replace('/', '\\')
            
            # Remove duplicate backslashes (normalize to single backslash in internal string)
            while '\\\\' in f:
                f = f.replace('\\\\', '\\')
            
            # Extract the actual folder name (everything after 'downloads\')
            downloads_marker = r'downloads\\'
            if 'downloads\\' in f:
                folder_name = f.split('downloads\\')[-1]
            elif 'downloads' in f:
                folder_name = f.split('downloads')[-1].lstrip('\\')
            else:
                # If the prefix isn't there at all, the whole string is the folder name
                folder_name = f
            
            # Construct the clean path: target_prefix + \ + folder_name
            clean_path = os.path.join(target_prefix, folder_name)
            
            if folder != clean_path:
                updated += 1
            new_folders.append(clean_path)
            
        page['folders'] = new_folders
        
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print(f"Standardized {updated} paths.")

if __name__ == "__main__":
    standardize_paths()
