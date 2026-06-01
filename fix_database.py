
import re

def fix_database_json():
    path = r"h:\Tool_tucode\AutoDangbaifanpage+comment\database.json"
    prefix = r"C:\\Users\\congt\\Documents\\Antigravity_folder\\downloads\\"
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    for i in range(len(lines)):
        line = lines[i]
        stripped = line.strip()
        
        # Detect lines that look like a folder name but aren't quoted/prefixed
        # These are usually indented and followed by ] or another folder
        # We look for lines that don't start with JSON structural characters
        if stripped and not stripped.startswith(('"', '[', ']', '{', '}', ':', 'true', 'false', 'null')) and not stripped[0].isdigit():
            # This is likely one of the missing paths
            # We need to add the prefix, quotes, and potentially a comma to the previous line
            folder_name = stripped
            new_path = f"{prefix}{folder_name}"
            # Escape backslashes for JSON
            new_path_json = new_path.replace('\\', '\\\\')
            
            # Add comma to previous line if it doesn't have one and is a folder entry
            if len(new_lines) > 0:
                prev_line = new_lines[-1]
                if prev_line.strip().endswith('"') and not prev_line.strip().endswith(','):
                    new_lines[-1] = prev_line.replace('"', '",')
            
            # Construct the new line with original indentation
            indent = line[:line.find(stripped)]
            new_lines.append(f'{indent}"{new_path_json}"\n')
        else:
            # Check for a specific case where a quoted path is followed by another path but missing a comma
            if stripped.startswith('"') and stripped.endswith('"') and i + 1 < len(lines):
                next_stripped = lines[i+1].strip()
                if next_stripped and not next_stripped.startswith((']', '}')):
                    # Might need a comma
                    if not stripped.endswith(','):
                        line = line.replace('"', '",', 1) # This is tricky, let's just add at the end
                        line = line.rstrip() + ',\n'
            
            new_lines.append(line)
            
    # Remove extra empty lines inside arrays (like lines 206, 207)
    final_lines = []
    for j in range(len(new_lines)):
        line = new_lines[j]
        if line.strip() == "" and j > 0 and j < len(new_lines) - 1:
            if new_lines[j-1].strip().startswith('"') or new_lines[j-1].strip() == "[": # Inside an array or after path
                if new_lines[j+1].strip() == "]":
                    continue # Skip empty line before closing bracket
        final_lines.append(line)

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    
    print("Database fixed and paths updated.")

if __name__ == "__main__":
    fix_database_json()
