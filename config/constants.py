"""Application constants for VIMC Manifest Cleaner v2.0.

Contains application metadata, UI text, colors, and ship type configurations.
"""

from typing import Dict, List, Any

# Application metadata
APP_TITLE = "Manifest Cleaner"
APP_VERSION = "3.0.0"
APP_AUTHOR_VI = "Developed by: Tiền - Cảng Tân Thuận"
APP_AUTHOR_EN = "Developed by: Tien - Tan Thuan Port"

# Ship type constants
SHIP_TYPES = {
    "MARINER": "VIMC_MarinerType",      # Description first, weight in KGS
    "PIONEER": "VIMC_PioneerType",       # Weight first (TONS), then description
    "NAVIGATOR": "VIMC_PioneerType",     # Same as Pioneer
    "STAR": "VIMC_PioneerType",          # Same as Pioneer (e.g., BIEN DONG STAR)
}

# Keywords for ship type detection from filename
SHIP_KEYWORDS = {
    "MARINER": ["MARINER"],
    "PIONEER_TYPE": ["PIONEER", "NAVIGATOR", "STAR"],
}

# Operators for VIMC
OPERATOR_SOC = "SVM"  # SOC operator code
OPERATOR_COC = "VMC"  # COC operator code

# Keywords for SOC/COC detection
SOC_KEYWORDS = ["SOC LADEN", "SOC EMPTY", "SOC"]
COC_KEYWORDS = ["COC LADEN", "COC"]
EMPTY_KEYWORDS = ["EMPTY", "CHUYEN RONG", "CONTAINER RONG"]

# UI Colors
COLORS = {
    "primary": "#0F52BA",      # Sapphire/VIMC Dark Blue
    "success": "#0F9D58",      # Rich Green
    "danger": "#DB4437",       # Material Red
    "warning": "#F4B400",      # Amber Yellow
    "bg": "#F1F5F9",           # Very soft gray-blue background (slate-50)
    "card_bg": "#FFFFFF",      # White card background
    "text": "#0F172A",         # Very dark slate gray (almost black)
    "text_light": "#64748B",   # Slate gray for secondary text
    "border": "#E2E8F0",       # Slate border color
    "mariner": "#1D70B8",      # Modern blue for Mariner
    "pioneer": "#10B981",      # Modern emerald green for Pioneer type
}


# Default UI text (fallback if strings file not found)
UI_TEXT = {
    "vi": {
        "app_title": "Manifest Cleaner",
        "app_subtitle": "VIMC Manifest Cleaner",
        "btn_choose_file": "📂 Chọn File Manifest",
        "btn_process": "🔄 Xử lý",
        "btn_preview": "👁️ Xem trước",
        "btn_save": "💾 Lưu file",
        "recent_files": "📂 Gần đây:",
        "no_recent": "Chưa có file nào",
        "status_ready": "Sẵn sàng",
        "status_processing": "Đang xử lý...",
        "status_done": "Hoàn thành!",
        "status_error": "Lỗi",
        "stats_containers": "Container:",
        "stats_full": "Full:",
        "stats_empty": "Empty:",
        "stats_soc": "SOC:",
        "stats_coc": "COC:",
        "ship_type": "Loại tàu:",
        "ship_mariner": "🚢 MARINER",
        "ship_pioneer": "🚢 PIONEER/NAVIGATOR/STAR",
        "ship_unknown": "❓ Chưa xác định",
        "menu_language": "Ngôn ngữ",
        "menu_auto_open": "Tự động mở file",
        "menu_shortcuts": "Phím tắt",
        "menu_about": "Thông tin",
    },
    "en": {
        "app_title": "Manifest Cleaner",
        "app_subtitle": "VIMC Manifest Cleaner",
        "btn_choose_file": "📂 Choose Manifest File",
        "btn_process": "🔄 Process",
        "btn_preview": "👁️ Preview",
        "btn_save": "💾 Save File",
        "recent_files": "📂 Recent:",
        "no_recent": "No recent files",
        "status_ready": "Ready",
        "status_processing": "Processing...",
        "status_done": "Done!",
        "status_error": "Error",
        "stats_containers": "Containers:",
        "stats_full": "Full:",
        "stats_empty": "Empty:",
        "stats_soc": "SOC:",
        "stats_coc": "COC:",
        "ship_type": "Ship type:",
        "ship_mariner": "🚢 MARINER",
        "ship_pioneer": "🚢 PIONEER/NAVIGATOR/STAR",
        "ship_unknown": "❓ Unknown",
        "menu_language": "Language",
        "menu_auto_open": "Auto open file",
        "menu_shortcuts": "Shortcuts",
        "menu_about": "About",
    }
}

# Output column names
OUTPUT_COLUMNS = [
    "STT",
    "Số Vận Đơn",
    "Số Container",
    "Số niêm chì",
    "Số niêm chì 1",
    "Chủ hàng",
    "Kích cỡ",
    "Loại Container",
    "Hãng khai thác",
    "Loại hàng",
    "F/E",
    "Trọng lượng (Tấn)",
    "Hàng hóa",
    "Số lượng",
    "Độ chính xác (%)",
    "Ghi chú",
]

# Mapping from intermediate data keys to output column names
OUTPUT_COLUMN_MAPPING = {
    "BL_No": "Số Vận Đơn",
    "Container_No": "Số Container",
    "Seal_No": "Số niêm chì",
    "Cleaned_Consignee_Name_For_Output": "Chủ hàng",
    "Size_Type": "Kích cỡ",
    "ISO_Size": "Loại Container",
    "Operator": "Hãng khai thác",
    "Cargo_Type": "Loại hàng",
    "FE_Status": "F/E",
    "Weight_Value": "Trọng lượng (Tấn)",
    "Description": "Hàng hóa",
    "Confidence": "Độ chính xác (%)",
    "Warning": "Ghi chú",
}

# VIMC-specific input column names
VIMC_INPUT_COLUMNS = {
    "party_info": "PARTICULARS FURNISHED BY SHIPPER",
    "bl_no": "B/L NO:",
    "marks_numbers": "MARKS & NUMBERS",
    "desc_goods": "DISCRIPTION OF GOODS",
}

# Excel formatting
EXCEL_FORMATTING = {
    "seal_invalid_bg_color": "#FFFF00",    # Yellow for invalid seal
    "empty_container_bg_color": "#DAEEF3", # Light blue for empty
    "max_column_width": 40,
    "output_sheet_name": "Processed_Manifest",
}

# Logic thresholds for F/E determination
FE_THRESHOLDS = {
    "tare_40ft": 5.0,
    "tare_20ft": 3.0,
    "tare_40rf": 4.8,
    "tare_20rf": 3.0,
    "cargo_weight_empty": 0.05,
}
