import os
import shutil

def clean_project():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Những thứ cần dọn
    targets_to_delete = [
        "__pycache__",
        ".pytest_cache",
        ".DS_Store", # File rác của Mac
    ]
    
    # 1. Quét và xóa các thư mục rác
    count = 0
    for root, dirs, files in os.walk(project_dir):
        for d in dirs:
            if d in targets_to_delete:
                path = os.path.join(root, d)
                try:
                    shutil.rmtree(path)
                    count += 1
                    print(f"🧹 Đã xóa: {path}")
                except Exception as e:
                    print(f"Lỗi khi xóa {path}: {e}")

    print(f"\n✨ Dọn dẹp hoàn tất! (Xóa {count} thư mục rác). Project đã sạch như mới tải từ Github!")

if __name__ == "__main__":
    clean_project()