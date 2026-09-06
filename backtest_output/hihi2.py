import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Cấu hình font chữ chuẩn học thuật
from pathlib import Path
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']

fig, ax = plt.subplots(figsize=(13, 5.5), facecolor='white')
ax.set_xlim(0, 14)
ax.set_ylim(0, 5.5)
ax.axis('off')

# Dữ liệu 8 bước
boxes = [
    ("Bước 1:\nChọn chiến lược", "Giá trị - Tăng trưởng\n- Cổ tức"),
    ("Bước 2:\nTùy chỉnh", "Chỉnh tham số\n- Tùy biến bộ lọc"),
    ("Bước 3:\nSàng lọc", "~1.500+ mã\n→ Danh sách rút gọn"),
    ("Bước 4:\nXếp hạng", "FSS Smart Rank\n"), 
    ("Bước 5:\nPhân tích", "Cơ bản - Định giá\n- Kỹ thuật"),
    ("Bước 6:\nDiễn giải (AI)", "VinanceAI\nthấu hiểu ngữ cảnh"),
    ("Bước 7:\nSo sánh bối cảnh", "VN-Index\n- Bản đồ nhiệt ngành"),
    ("Bước 8:\nTheo dõi", "Danh mục\n- Cảnh báo rủi ro")
]

# Tọa độ mô hình chữ U (Rút ngắn trục Y để mũi tên dọc = mũi tên ngang)
x_centers = [2.2, 5.4, 8.6, 11.8, 11.8, 8.6, 5.4, 2.2]
y_centers = [3.8, 3.8, 3.8, 3.8, 1.8, 1.8, 1.8, 1.8]

box_w = 2.8
box_h = 1.6

# Vẽ các ô chữ nhật
for i in range(8):
    x, y = x_centers[i], y_centers[i]
    rect = mpatches.Rectangle((x - box_w/2, y - box_h/2), box_w, box_h, 
                              facecolor='#FAFAFA', edgecolor='black', linewidth=1.2, zorder=2)
    ax.add_patch(rect)
    
    title, sub = boxes[i]
    ax.text(x, y + 0.25, title, ha='center', va='center', fontsize=12, fontweight='bold', linespacing=1.4, zorder=3)
    ax.text(x, y - 0.35, sub, ha='center', va='center', fontsize=11, linespacing=1.4, zorder=3)

# Định dạng mũi tên 
arrow_props = dict(arrowstyle="-|>", color='black', lw=1.2, mutation_scale=15)

for i in range(3):
    ax.annotate('', xy=(x_centers[i+1] - box_w/2, y_centers[i]), 
                xytext=(x_centers[i] + box_w/2, y_centers[i]), arrowprops=arrow_props)

ax.annotate('', xy=(x_centers[4], y_centers[4] + box_h/2), 
            xytext=(x_centers[3], y_centers[3] - box_h/2), arrowprops=arrow_props)

for i in range(4, 7):
    ax.annotate('', xy=(x_centers[i+1] + box_w/2, y_centers[i]), 
                xytext=(x_centers[i] - box_w/2, y_centers[i]), arrowprops=arrow_props)

# Tiêu đề 
ax.text(7, 5.1, "LUỒNG QUY TRÌNH KHÉP KÍN (FSS END-TO-END WORKFLOW)", 
        ha='center', va='center', fontsize=15, fontweight='bold')

# Chú thích
ax.text(7, 0.4, "* Nguồn: Nhóm TheFinWings đề xuất. FSS hỗ trợ phân tích, quyết định đầu tư thuộc về người dùng.", 
        ha='center', va='center', fontsize=11, fontstyle='italic')

here = Path(__file__).parent
plt.savefig(here /'FSS_Workflow_Equal_Arrows.png', dpi=300, bbox_inches='tight')