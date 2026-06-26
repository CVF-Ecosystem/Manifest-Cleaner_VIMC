# VIMC Manifest Cleaner v3.0

🚢 Công cụ xử lý Cargo Manifest cho tàu VIMC (MARINER, PIONEER, NAVIGATOR, BIEN DONG STAR).

## ✨ Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 🔍 **Auto-detect ship type** | Tự động nhận dạng loại tàu từ tên file |
| 🖱️ **One-click processing** | Chọn file → xử lý tự động |
| 👁️ **Preview window** | Xem trước dữ liệu với filter, sort, save |
| 🔊 **Sound notifications** | Âm thanh thông báo hoàn thành/lỗi |
| 🌐 **Multilingual** | Tiếng Việt / English |
| 📂 **Recent files** | Danh sách file gần đây với thống kê |
| ⌨️ **Keyboard shortcuts** | Ctrl+O, F5, F1 |
| 📄 **Auto-open file** | Tự động mở file sau khi lưu (tùy chọn) |

## 📁 Cấu trúc project

```
VIMC/
├── vimc_app.py           # 🚀 Entry point - Chạy file này
├── VIMC_Manifest.spec    # 📦 Cấu hình đóng gói PyInstaller
├── app_config.json       # Cấu hình ứng dụng cục bộ (tự tạo)
├── strings_vi.ini        # Ngôn ngữ Tiếng Việt
├── strings_en.ini        # Ngôn ngữ English
├── config/               # Module cấu hình
│   ├── constants.py      # Hằng số ứng dụng
│   └── mappings.py       # Bảng mapping SIZE/ISO
├── core/                 # Module xử lý chính
│   ├── excel_handler.py  # Đọc/ghi file Excel
│   ├── parsers.py        # Phân tích dữ liệu container
│   ├── processors.py     # Logic xử lý business
│   └── ship_detector.py  # Nhận dạng loại tàu
├── gui/                  # Module giao diện
│   └── main_window.py    # Cửa sổ chính + Preview window
├── utils/                # Tiện ích
│   └── helpers.py        # Hàm hỗ trợ
├── tests/                # Unit tests (26 tests)
│   └── test_vimc_modules.py
└── logs/                 # Log files
```

## 🚀 Cách sử dụng

### Chạy ứng dụng

```bash
cd VIMC
python vimc_app.py
```

### Build thành .exe

```bash
pip install pyinstaller
pyinstaller VIMC_Manifest.spec --clean -y
```

## ⌨️ Phím tắt

| Phím | Chức năng |
|------|-----------|
| `Ctrl+O` | Chọn file manifest |
| `F5` | Xử lý file |
| `F1` | Hiển thị phím tắt |

## 🚢 Định dạng Manifest hỗ trợ

> Định dạng phụ thuộc vào PLD (Hải Phòng/Đà Nẵng), không phụ thuộc tên tàu.

### 1. Hải Phòng Format (PIONEER style)
- **Đặc điểm**: Trọng lượng **TRƯỚC** (TẤN), mô tả hàng **SAU**
- **Ví dụ**: `VIMU2300126 | A29560648 | 20GP | 18 | VAN EP`

### 2. Đà Nẵng Format
- **Đặc điểm**: Mô tả **TRƯỚC**, trọng lượng **SAU** (KGS → tự động convert TONS)
- **Ví dụ**: `VIMU6252197 | A29005256 | 40HC | VO LON | 8000`

### 3. MARINER Format (legacy)
- **Đặc điểm**: Mô tả **TRƯỚC**, trọng lượng **SAU** (KGS)
- **Ví dụ**: `VNLU3097432 | VMC134321 | 20DC | GẠCH MEN | 27,000`

### ✅ Mixed Format Support
Xử lý tốt manifest chứa **hỗn hợp** nhiều định dạng trong cùng 1 file.


## 📊 Output columns

| Cột | Mô tả |
|-----|-------|
| STT | Số thứ tự |
| BL No. | Số Bill of Lading |
| Số lượng | Số container cùng B/L |
| Số cont | Container number |
| Loại | ISO code (20GP, 40HC...) |
| Tên hàng | Mô tả hàng hóa |
| Trọng lượng | Trọng lượng (KG) |
| Số seal | Seal number |
| F/E | Full/Empty |
| Shipper | Người gửi |
| Consignee | Người nhận |
| Notify | Thông báo |
| Hãng khai thác | SOC/COC |
| Loại hàng | GENERAL/REEFER... |

## 🧪 Chạy tests

```bash
cd VIMC
python -m pytest tests/test_vimc_modules.py -v
```

## 📝 Changelog

### v3.1.0 (Jun 2026)
- 🎨 **Giao diện phẳng & tương phản cao**: Nâng cấp nút bấm sang dạng phẳng (Flat), tối ưu hóa màu sắc thương hiệu VIMC (Navy, Emerald Green, Slate) giúp cải thiện độ tương phản và trực quan hơn.
- ⚙️ **Ánh xạ loại hàng (Tank → General)**: Điều chỉnh cấu hình loại hàng cho vỏ tank (`20TK`, `40TK`, `22T1`, `42T1`) luôn là `GENERAL` (hoặc `EMPTY` nếu container rỗng).
- 🔧 **Sửa lỗi AttributeError**: Sửa lỗi crash khi nạp file do thiếu hàm hiển thị loại tàu `_update_ship_type_display` và nhãn UI tương ứng.
- 📦 **Đóng gói PyInstaller hoàn thiện**: Tự động nhúng file ngôn ngữ vào file `.exe` (`sys._MEIPASS`) và sửa lỗi ghi cấu hình/logs cục bộ.

### v3.0.0 (Jan 2026)
- ✨ **Dual format support**: Hỗ trợ cả Hải Phòng và Đà Nẵng trong cùng 1 file
- ✨ Auto-detect Da Nang format (POL: CANG DA NANG)
- ✨ Fallback parsing: PIONEER → DANANG
- ✨ Auto KGS → TONS conversion for Da Nang cargo
- 🔧 Fixed SOC detection từ Description column
- 🔧 Fixed ISO-to-VTOS size mapping (22G1 → 20DC)

### v2.0.0 (Dec 2025)
- ✨ Refactor hoàn toàn sang kiến trúc modular
- ✨ Auto-detect ship type (MARINER vs PIONEER/NAVIGATOR/STAR)
- ✨ Preview window với filter, sort, save trực tiếp
- ✨ Sound notifications (success/error)
- ✨ Compact UI với ship type indicator
- ✨ Multilingual support (VI/EN)
- ✨ Recent files với stats
- ✨ Unit tests (26 tests)

### v1.0.0
- Phiên bản gốc monolithic

## 📋 Requirements

```
pandas>=2.0.0
openpyxl>=3.1.0
tkinterdnd2>=0.3.0
pytest>=7.0.0
```

## 👤 Tác giả

**Developed by: Tiền - Cảng Tân Thuận**

---
*VIMC Manifest Cleaner - Xử lý manifest nhanh chóng và chính xác* 🚢
