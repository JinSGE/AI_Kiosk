import json
import os

file_path = r"C:/Users/sunge/OneDrive/바탕 화면/SE/AI-API/app/data/menu_data.json"

# Verify file exists
print("File exists:", os.path.exists(file_path))

# Try to read and parse the JSON
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        menu_data = json.load(f)
    
    # Print some basic validation
    print("\nJSON Successfully Parsed!")
    print("\nTop-level keys:", list(menu_data.keys()))
    
    # Validate specific sections
    print("\nCategories:", menu_data.get('categories', {}).keys())
    print("\nMenus count:", len(menu_data.get('menus', [])))
    print("\nQuantities:", menu_data.get('quantities', {}))
    print("\nOption Types:", menu_data.get('option_types', {}))

except json.JSONDecodeError as e:
    print(f"JSON Parsing Error: {e}")
except Exception as e:
    print(f"An error occurred: {e}")