"""Quick setup script to create all necessary files."""

from pathlib import Path

project_root = Path("D:/Data Pre-Processing")

# Create directory structure
dirs = [
    "src/sar_processor/config",
    "src/sar_processor/processors",
    "src/sar_processor/utils",
    "src/sar_processor/cli",
    "data/inputs",
    "data/outputs",
    "logs"
]

for dir_path in dirs:
    (project_root / dir_path).mkdir(parents=True, exist_ok=True)

# Create empty __init__.py files
init_files = [
    "src/sar_processor/__init__.py",
    "src/sar_processor/config/__init__.py",
    "src/sar_processor/processors/__init__.py",
    "src/sar_processor/utils/__init__.py",
    "src/sar_processor/cli/__init__.py",
]

for init_file in init_files:
    init_path = project_root / init_file
    if not init_path.exists():
        init_path.write_text("# Package initialization\n")

print("✅ Project structure created successfully!")
print("Now copy the code content into the respective files.")
