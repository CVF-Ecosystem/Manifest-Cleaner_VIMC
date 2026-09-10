"""Excel handling for VIMC Manifest Cleaner.

Supports two manifest formats:
1. MARINER type: Description first, weight in KGS
2. PIONEER/NAVIGATOR/STAR type: Weight first (TONS), then description
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

import pandas as pd

try:
    from xlsxwriter.utility import xl_col_to_name
    XLSXWRITER_AVAILABLE = True
except ImportError:
    xl_col_to_name = None
    XLSXWRITER_AVAILABLE = False

from config.constants import (
    OUTPUT_COLUMNS,
    OUTPUT_COLUMN_MAPPING,
    VIMC_INPUT_COLUMNS,
    EXCEL_FORMATTING,
    OPERATOR_SOC,
    OPERATOR_COC,
)
from config.mappings import BL_NO_IDENTIFIER, PARTY_MARKERS
from core.parsers import (
    parse_mariner_container_detail,
    parse_pioneer_container_detail,
    parse_danang_container_detail,
    parse_marks_container,
    parse_weight_kg,
    parse_weight_tons,
    is_empty_description,
    clean_seal_number,
)
from core.processors import (
    determine_fe,
    determine_cargo_type,
    determine_operator,
    is_empty_bl,
    get_iso_size,
    get_vtos_size,
    clean_party_name,
    refine_description_column,
)
from core.ship_detector import ShipType, detect_ship_type
from utils.normalization import normalize_text

logger = logging.getLogger(__name__)


class VimcExcelHandler:
    """Handler for reading and processing VIMC manifest Excel files."""
    
    def __init__(self, config: Optional[Any] = None):
        """Initialize handler.
        
        Args:
            config: Optional INI config object (for backward compatibility)
        """
        self.config = config
        self.ship_type: ShipType = ShipType.UNKNOWN
        self.df_raw: Optional[pd.DataFrame] = None
        self.intermediate_data: List[Dict[str, Any]] = []
        self.final_df: Optional[pd.DataFrame] = None
        self.header_row_idx: int = -1
        
        # Column names from config or defaults
        self.col_party_info = VIMC_INPUT_COLUMNS["party_info"]
        self.col_marks_numbers = VIMC_INPUT_COLUMNS["marks_numbers"]
        self.col_desc_goods = VIMC_INPUT_COLUMNS["desc_goods"]
        
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """Pre-validate Excel file before processing.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(file_path)
        
        # Check file exists
        if not path.exists():
            return False, f"File không tồn tại: {path.name}"
        
        # Check file extension
        valid_extensions = ['.xlsx', '.xls', '.xlsm']
        if path.suffix.lower() not in valid_extensions:
            return False, f"Định dạng file không hợp lệ. Hỗ trợ: {', '.join(valid_extensions)}"
        
        # Check file size (max 50MB)
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > 50:
            return False, f"File quá lớn ({file_size_mb:.1f}MB). Tối đa: 50MB"
        
        # Check if file is readable (not locked)
        try:
            with open(path, 'rb') as f:
                f.read(1)
        except PermissionError:
            return False, "File đang mở bởi chương trình khác. Vui lòng đóng và thử lại."
        except IOError as e:
            return False, f"Không thể đọc file: {e}"
        
        return True, ""
    
    def read_excel(self, file_path: str) -> Tuple[pd.DataFrame, int]:
        """Read VIMC manifest Excel file.
        
        Args:
            file_path: Path to Excel file
            
        Returns:
            Tuple of (DataFrame, header_row_index)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If header not found or missing columns
        """
        path = Path(file_path)
        
        # Pre-validate
        is_valid, error_msg = self.validate_file(file_path)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Detect ship type
        self.ship_type = detect_ship_type(file_path)
        logger.info(f"Detected ship type: {self.ship_type.value}")
        
        # Determine engine based on actual file content (magic bytes),
        # not just extension - some .xls files are actually XLSX format
        try:
            with open(file_path, 'rb') as _f:
                _magic = _f.read(4)
            is_xlsx_format = (_magic == b'PK\x03\x04')  # ZIP/XLSX signature
        except Exception:
            is_xlsx_format = path.suffix.lower() in ('.xlsx', '.xlsm')
        engine = 'openpyxl' if is_xlsx_format else 'xlrd'
        logger.info(f"Detected {'XLSX' if is_xlsx_format else 'XLS'} format for: {path.name}")
        
        # Read peek rows to find header
        peek_rows = 20
        try:
            df_peek = pd.read_excel(
                file_path,
                sheet_name=0,
                header=None,
                nrows=peek_rows,
                keep_default_na=False,
                engine=engine
            )
        except Exception as e:
            # Try with default engine
            logger.warning(f"Error with engine {engine}, trying default: {e}")
            df_peek = pd.read_excel(
                file_path,
                sheet_name=0,
                header=None,
                nrows=peek_rows,
                keep_default_na=False
            )
        
        # Find header row
        header_idx = self._find_header_row(df_peek)
        if header_idx == -1:
            raise ValueError(
                f"Không tìm thấy dòng tiêu đề trong {peek_rows} dòng đầu. "
                f"Cần có cột: '{self.col_party_info}', '{self.col_marks_numbers}', '{self.col_desc_goods}'"
            )
        
        self.header_row_idx = header_idx
        
        # Read full data
        try:
            df = pd.read_excel(
                file_path,
                sheet_name=0,
                header=header_idx,
                keep_default_na=False,
                engine=engine
            )
        except Exception as e:
            df = pd.read_excel(
                file_path,
                sheet_name=0,
                header=header_idx,
                keep_default_na=False
            )
        
        # Normalize column names
        df.columns = [
            ' '.join(re.sub(r'[\n\r\t]+', ' ', str(col)).split()).strip()
            for col in df.columns
        ]
        
        # Verify required columns
        self._verify_columns(df)
        
        self.df_raw = df
        return df, header_idx
    
    def _find_header_row(self, df_peek: pd.DataFrame) -> int:
        """Find header row index by looking for expected column names.
        
        Args:
            df_peek: First N rows of Excel file
            
        Returns:
            Header row index or -1 if not found
        """
        # Primary keywords to search for (more flexible matching)
        # For MARKS & NUMBERS column
        marks_keywords = ["marks", "marks & numbers", "marks&numbers"]
        
        # For description column (various formats)
        desc_keywords = [
            "description", "discription", "desc",
            "no. of packages", "packages", "mô tả hàng"
        ]
        
        # For party/shipper column
        party_keywords = [
            "shipper", "consignee", "particulars", "party",
            "chủ hàng", "người gửi"
        ]
        
        for idx, row in df_peek.iterrows():
            row_text = ' '.join([
                ' '.join(re.sub(r'[\n\r\t]+', ' ', str(val)).split()).strip().lower()
                for val in row.tolist()
            ])
            
            # Check if this row contains header keywords
            found_marks = any(kw in row_text for kw in marks_keywords)
            found_desc = any(kw in row_text for kw in desc_keywords)
            found_party = any(kw in row_text for kw in party_keywords)
            
            # Need at least 2 out of 3 key columns
            matches = sum([found_marks, found_desc, found_party])
            if matches >= 2:
                logger.info(f"Found header at row index {idx} (matches: {matches}/3)")
                
                # Store actual column names for this file
                self._detect_actual_columns(row)
                return idx
        
        return -1
    
    def _detect_actual_columns(self, header_row: pd.Series) -> None:
        """Detect actual column names from header row.
        
        Args:
            header_row: Row containing headers
        """
        for val in header_row.tolist():
            cell = ' '.join(re.sub(r'[\n\r\t]+', ' ', str(val)).split()).strip()
            cell_lower = cell.lower()
            
            # Detect party info column
            if any(kw in cell_lower for kw in ["shipper", "consignee", "particulars"]):
                self.col_party_info = cell
                logger.debug(f"Detected party column: {cell}")
            
            # Detect marks column
            if "marks" in cell_lower:
                self.col_marks_numbers = cell
                logger.debug(f"Detected marks column: {cell}")
            
            # Detect description column
            if any(kw in cell_lower for kw in ["description", "discription", "packages"]):
                self.col_desc_goods = cell
                logger.debug(f"Detected description column: {cell}")
    
    def _verify_columns(self, df: pd.DataFrame) -> None:
        """Verify required columns exist (with flexible matching).
        
        Args:
            df: DataFrame to verify
            
        Raises:
            ValueError: If required columns are missing
        """
        # Try to find columns with flexible matching
        cols_lower = {col.lower(): col for col in df.columns}
        
        # Find marks column
        marks_col = None
        for col in df.columns:
            if "marks" in col.lower():
                marks_col = col
                self.col_marks_numbers = col
                break
        
        # Find description column  
        desc_col = None
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ["description", "discription", "packages"]):
                desc_col = col
                self.col_desc_goods = col
                break
        
        # Find party column
        party_col = None
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ["shipper", "consignee", "particulars"]):
                party_col = col
                self.col_party_info = col
                break
        
        missing = []
        if not marks_col:
            missing.append("MARKS & NUMBERS")
        if not desc_col:
            missing.append("DESCRIPTION/PACKAGES")
        if not party_col:
            missing.append("SHIPPER/CONSIGNEE")
        
        if missing:
            raise ValueError(
                f"Thiếu cột bắt buộc: {', '.join(missing)}. "
                f"Các cột có: {df.columns.tolist()[:6]}..."
            )
    
    def parse_manifest_data(
        self,
        df: pd.DataFrame,
        header_row_idx: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Parse manifest data into intermediate format.
        
        Args:
            df: DataFrame with manifest data
            header_row_idx: Header row index for Excel row calculation
            
        Returns:
            List of container dictionaries
        """
        self.intermediate_data = []
        
        current_bl: Dict[str, Any] = {}
        bl_start_row_idx: Optional[int] = None
        
        total_rows = len(df)
        
        for idx, row in df.iterrows():
            if progress_callback and idx % 50 == 0:
                progress_callback(idx, total_rows, f"Đọc dữ liệu thô: {idx}/{total_rows} dòng")
                
            excel_row = idx + header_row_idx + 2  # +2 for 1-based and header
            
            first_cell = self._get_cell_value(row.iloc[0])
            desc_text = self._get_cell_value(row.get(self.col_desc_goods, ""))
            marks_text = self._get_cell_value(row.get(self.col_marks_numbers, ""))
            
            # Check for B/L start
            if BL_NO_IDENTIFIER.lower() in first_cell.lower():
                # Finalize previous B/L
                if current_bl.get("BL_No"):
                    self._finalize_bl_group(current_bl)
                
                # Extract B/L number
                bl_no = self._extract_bl_number(row)
                if bl_no:
                    current_bl = {
                        "BL_No": bl_no,
                        "Shipper": [],
                        "Consignee": [],
                        "Notify": [],
                        "DescGoodsRaw": [],
                        "MarksNumbersRaw": [],
                        "OperatorStatus": "COC",
                        "IsExplicitlyEmpty": False,
                        "Master_BL_Group_ID": bl_no,
                    }
                    bl_start_row_idx = idx
                    
                    # Get party info from next row
                    self._extract_party_info(df, idx + 1, current_bl)
                    
                    logger.info(f"Started B/L: {bl_no} at row {excel_row}")
                    
                    # IMPORTANT: Also collect desc/marks from B/L row itself
                    if marks_text:
                        current_bl["MarksNumbersRaw"].append(marks_text)
                    if desc_text:
                        current_bl["DescGoodsRaw"].append(desc_text)
                        self._check_operator_status(desc_text, current_bl)
                continue
            
            # Collect data for current B/L (skip party info row)
            if current_bl.get("BL_No") and bl_start_row_idx is not None and idx != bl_start_row_idx + 1:
                if marks_text:
                    current_bl["MarksNumbersRaw"].append(marks_text)
                
                if desc_text:
                    current_bl["DescGoodsRaw"].append(desc_text)
                    
                    # Check for SOC/COC/Empty indicators
                    self._check_operator_status(desc_text, current_bl)
        
        # Finalize last B/L
        if current_bl.get("BL_No"):
            self._finalize_bl_group(current_bl)
        
        return self.intermediate_data
    
    def _get_cell_value(self, cell: Any) -> str:
        """Get cell value as string."""
        if pd.isna(cell) or cell == '':
            return ""
        return str(cell).strip()
    
    def _extract_bl_number(self, row: pd.Series) -> Optional[str]:
        """Extract B/L number from row."""
        if len(row) > 2:
            potential_bl = self._get_cell_value(row.iloc[2])
            if potential_bl:
                return potential_bl.split()[0]
        return None
    
    def _extract_party_info(
        self,
        df: pd.DataFrame,
        party_row_idx: int,
        bl_data: Dict[str, Any]
    ) -> None:
        """Extract shipper/consignee/notify from party info row."""
        if party_row_idx >= len(df):
            return
        
        party_row = df.iloc[party_row_idx]
        party_text = self._get_cell_value(party_row.iloc[0])
        
        if not party_text:
            return
        
        current_list: Optional[List[str]] = None
        
        for line in party_text.split('\n'):
            line = line.strip()
            
            if line.startswith(PARTY_MARKERS["shipper"]):
                current_list = bl_data["Shipper"]
                line = line[2:].lstrip()
            elif line.startswith(PARTY_MARKERS["consignee"]):
                current_list = bl_data["Consignee"]
                line = line[2:].lstrip()
            elif line.startswith(PARTY_MARKERS["notify"]):
                current_list = bl_data["Notify"]
                line = line[2:].lstrip()
            
            if current_list is not None and line:
                current_list.append(line)
    
    def _check_operator_status(
        self,
        desc_text: str,
        bl_data: Dict[str, Any]
    ) -> None:
        """Check description for SOC/COC and empty indicators."""
        desc_upper = desc_text.upper()
        
        if "SOC LADEN" in desc_upper or "SOC EMPTY" in desc_upper:
            bl_data["OperatorStatus"] = "SOC"
            if "SOC EMPTY" in desc_upper:
                bl_data["IsExplicitlyEmpty"] = True
        elif "COC LADEN" in desc_upper and bl_data.get("OperatorStatus") != "SOC":
            bl_data["OperatorStatus"] = "COC"
        
        if is_empty_bl(desc_text):
            bl_data["IsExplicitlyEmpty"] = True
    
    def _finalize_bl_group(self, bl_data: Dict[str, Any]) -> None:
        """Finalize B/L group and extract containers."""
        bl_no = bl_data["BL_No"]
        shipper = "\n".join(bl_data["Shipper"]).strip()
        consignee = "\n".join(bl_data["Consignee"]).strip()
        notify = "\n".join(bl_data["Notify"]).strip()
        
        # Handle "SAME AS CONSIGNEE"
        if "SAME AS CONSIGNEE" in notify.upper() or "NHU NGUOI NHAN HANG" in notify.upper():
            notify = consignee
        
        cleaned_consignee = clean_party_name(consignee)
        full_desc = "\n".join(bl_data["DescGoodsRaw"])
        full_marks = "\n".join(bl_data.get("MarksNumbersRaw", []))
        
        # Determine final operator
        operator_status = bl_data.get("OperatorStatus", "COC")
        is_empty = bl_data.get("IsExplicitlyEmpty", False)
        
        # Re-check operator from full description using robust logic from processors
        operator_code, is_soc = determine_operator(
            full_desc, 
            default_operator="VMC", 
            soc_code=OPERATOR_SOC, 
            coc_code=OPERATOR_COC
        )
        
        # Override operator status if determined
        operator_status = "SOC" if is_soc else "COC"
        
        # Check if explicitly empty or description indicates empty
        if is_empty_bl(full_desc):
            is_empty = True
        
        operator_code = OPERATOR_SOC if operator_status == "SOC" else OPERATOR_COC
        
        logger.info(
            f"Finalizing B/L {bl_no}: Operator={operator_status}, "
            f"Code={operator_code}, Empty={is_empty}"
        )
        
        # Parse containers
        processed_containers = set()
        
        for line in full_desc.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Parse based on ship type with fallback to DANANG format
            parsed = None
            weight_tons = None
            confidence = 100  # Default: exact match
            match_type = ""
            warnings = []
            
            if self.ship_type == ShipType.MARINER:
                parsed = parse_mariner_container_detail(line)
                if parsed:
                    weight_tons = parse_weight_kg(parsed["weight_raw"])
                    match_type = "MARINER"
            else:  # PIONEER type - try PIONEER first, then DANANG as fallback
                parsed = parse_pioneer_container_detail(line)
                if parsed:
                    weight_tons = parse_weight_tons(parsed["weight_raw"])
                    match_type = "PIONEER"
                else:
                    # Fallback to DANANG format (desc before weight, weight in KGS)
                    parsed = parse_danang_container_detail(line)
                    if parsed:
                        # DANANG weight is in KGS, convert to TONS
                        weight_tons = parse_weight_kg(parsed["weight_raw"])
                        match_type = "DANANG_FALLBACK"
                        confidence = 80  # Fallback used
                        warnings.append("⚠️ Fallback DANANG format")
            
            if parsed:
                cont_no = parsed["container_no"]
                processed_containers.add(cont_no)
                
                weight_info = {"value": weight_tons, "unit": "TONS"} if weight_tons else None
                fe_status = determine_fe(
                    parsed["description"],
                    weight_info,
                    parsed["size_type"],
                    is_explicitly_empty=is_empty
                )
                
                iso_size = get_iso_size(parsed["size_type"])
                vtos_size = get_vtos_size(parsed["size_type"])
                cargo_type = determine_cargo_type(parsed["size_type"], fe_status)
                
                # Check for strange/unknown size type
                if not iso_size:
                    warnings.append(f"⚠️ Loại kích cỡ lạ ({parsed['size_type']})")
                
                # Check seal validity
                seal_cleaned = clean_seal_number(parsed["seal_no"])
                if seal_cleaned and not (seal_cleaned.isdigit() and len(seal_cleaned) == 6):
                    warnings.append("⚠️ Seal không hợp lệ")
                
                self.intermediate_data.append({
                    "BL_No": bl_no,
                    "Container_No": cont_no,
                    "Seal_No": seal_cleaned,
                    "Size_Type": vtos_size,  # Standardize for "Kích cỡ" column
                    "Operator": operator_code,
                    "ISO_Size": vtos_size,   # User request: "Loại Container" should also be VTOS format
                    "FE_Status": fe_status,
                    "Weight_Value": weight_tons,
                    "Weight_Unit": "TONS" if weight_tons else None,
                    "Description": normalize_text(parsed["description"]),
                    "Cargo_Type": cargo_type,
                    "Input_Remarks": "",
                    "Shipper": shipper,
                    "Consignee": consignee,
                    "Notify": notify,
                    "Cleaned_Consignee_Name_For_Output": cleaned_consignee,
                    "Master_BL_Group_ID": bl_data.get("Master_BL_Group_ID", bl_no),
                    "Confidence": confidence,
                    "Warning": " | ".join(warnings) if warnings else "",
                })
        
        # If empty, also check MARKS & NUMBERS
        if is_empty:
            for mark_line in full_marks.split('\n'):
                for cont_info in parse_marks_container(mark_line.strip()):
                    cont_no = cont_info["container_no"]
                    if cont_no not in processed_containers:
                        processed_containers.add(cont_no)
                        
                        size_type = cont_info.get("size_type")
                        vtos_size = get_vtos_size(size_type)
                        iso_size = get_iso_size(size_type)
                        cargo_type = determine_cargo_type(size_type, 'E')
                        
                        self.intermediate_data.append({
                            "BL_No": bl_no,
                            "Container_No": cont_no,
                            "Seal_No": None,
                            "Size_Type": vtos_size,  # Standardize
                            "Operator": operator_code,
                            "ISO_Size": vtos_size,   # Standardize per user request
                            "FE_Status": 'E',
                            "Weight_Value": None,
                            "Weight_Unit": None,
                            "Description": "EMPTY",
                            "Cargo_Type": cargo_type,
                            "Input_Remarks": "",
                            "Shipper": shipper,
                            "Consignee": consignee,
                            "Notify": notify,
                            "Cleaned_Consignee_Name_For_Output": cleaned_consignee,
                            "Master_BL_Group_ID": bl_data.get("Master_BL_Group_ID", bl_no),
                            "Confidence": 100,  # EMPTY from MARKS is explicit
                            "Warning": "",
                        })
                        
                        logger.info(f"Added empty container {cont_no} from MARKS")
        
        logger.info(f"B/L {bl_no}: Processed {len(processed_containers)} containers")
    
    def build_output_dataframe(
        self,
        intermediate_data: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> pd.DataFrame:
        """Build final output DataFrame.
        
        Args:
            intermediate_data: List of container dictionaries
            progress_callback: Optional callback for progress updates
            
        Returns:
            Formatted DataFrame ready for export
        """
        if not intermediate_data:
            return pd.DataFrame()
            
        if progress_callback:
            progress_callback(100, 100, "Đang xây dựng bảng dữ liệu đầu ra...")
        
        df = pd.DataFrame(intermediate_data)
        
        # Filter out rows without consignee
        df = df[
            df["Cleaned_Consignee_Name_For_Output"].notna() &
            (df["Cleaned_Consignee_Name_For_Output"].str.strip() != '')
        ].copy()
        
        if df.empty:
            return pd.DataFrame()
        
        # Calculate quantity per B/L
        df["Quantity_Temp"] = df.groupby("Master_BL_Group_ID")["Container_No"].transform("count")
        
        # Select and rename columns
        cols_to_keep = list(OUTPUT_COLUMN_MAPPING.keys()) + ["Quantity_Temp"]
        cols_available = [c for c in cols_to_keep if c in df.columns]
        
        result_df = df[cols_available].copy()
        result_df.rename(columns=OUTPUT_COLUMN_MAPPING, inplace=True)
        
        # Add STT column
        result_df.insert(0, "STT", range(1, len(result_df) + 1))
        
        # Add Seal 1 column (duplicate of Seal)
        seal_col = OUTPUT_COLUMN_MAPPING.get("Seal_No", "Số niêm chì")
        if seal_col in result_df.columns:
            consignee_col = OUTPUT_COLUMN_MAPPING.get("Cleaned_Consignee_Name_For_Output", "Chủ hàng")
            if consignee_col in result_df.columns:
                insert_pos = result_df.columns.get_loc(consignee_col)
                result_df.insert(insert_pos, "Số niêm chì 1", result_df[seal_col])
        
        # Rename Quantity_Temp
        if "Quantity_Temp" in result_df.columns:
            result_df.rename(columns={"Quantity_Temp": "Số lượng"}, inplace=True)
        
        # Round weight
        weight_col = OUTPUT_COLUMN_MAPPING.get("Weight_Value", "Trọng lượng (Tấn)")
        if weight_col in result_df.columns:
            result_df[weight_col] = pd.to_numeric(
                result_df[weight_col], errors="coerce"
            ).round(2)
        
        # Refine description for empty containers
        fe_col = OUTPUT_COLUMN_MAPPING.get("FE_Status", "F/E")
        goods_col = OUTPUT_COLUMN_MAPPING.get("Description", "Hàng hóa")
        if fe_col in result_df.columns and goods_col in result_df.columns:
            mask = result_df[fe_col] == 'E'
            result_df.loc[mask, goods_col] = "EMPTY"
        
        # Reorder columns
        final_cols = []
        for col in OUTPUT_COLUMNS:
            if col in result_df.columns:
                final_cols.append(col)
        for col in result_df.columns:
            if col not in final_cols:
                final_cols.append(col)
        
        self.final_df = result_df.reindex(columns=final_cols)
        return self.final_df
    
    def save_excel(
        self,
        output_path: str,
        df: Optional[pd.DataFrame] = None
    ) -> bool:
        """Save DataFrame to Excel with formatting.
        
        Args:
            output_path: Output file path
            df: DataFrame to save (uses self.final_df if not provided)
            
        Returns:
            True if saved successfully
        """
        if df is None:
            df = self.final_df
        
        if df is None or df.empty:
            logger.warning("No data to save")
            return False
        
        sheet_name = EXCEL_FORMATTING["output_sheet_name"]
        
        if not XLSXWRITER_AVAILABLE:
            # Save without formatting
            df.to_excel(output_path, index=False, sheet_name=sheet_name)
            logger.warning("Saved without formatting (xlsxwriter not available)")
            return True
        
        try:
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
                
                workbook = writer.book
                worksheet = writer.sheets[sheet_name]
                
                # Formats
                yellow_format = workbook.add_format({
                    'bg_color': EXCEL_FORMATTING["seal_invalid_bg_color"]
                })
                light_blue_format = workbook.add_format({
                    'bg_color': EXCEL_FORMATTING["empty_container_bg_color"]
                })
                
                # Conditional formatting for seal
                seal_col = OUTPUT_COLUMN_MAPPING.get("Seal_No", "Số niêm chì")
                if seal_col in df.columns and xl_col_to_name:
                    seal_idx = df.columns.get_loc(seal_col)
                    col_letter = xl_col_to_name(seal_idx)
                    last_row = len(df) + 1
                    
                    formula = (
                        f'=AND(NOT(ISBLANK({col_letter}2)), '
                        f'NOT(AND(ISNUMBER(--TRIM({col_letter}2)), '
                        f'OR(LEN(TRIM({col_letter}2))=6, LEN(TRIM({col_letter}2))=7))))'
                    )
                    
                    if last_row > 1:
                        worksheet.conditional_format(
                            f'{col_letter}2:{col_letter}{last_row}',
                            {'type': 'formula', 'criteria': formula, 'format': yellow_format}
                        )
                
                # Conditional formatting for empty containers
                fe_col = OUTPUT_COLUMN_MAPPING.get("FE_Status", "F/E")
                if fe_col in df.columns and xl_col_to_name:
                    fe_idx = df.columns.get_loc(fe_col)
                    fe_letter = xl_col_to_name(fe_idx)
                    last_row = len(df) + 1
                    num_cols = len(df.columns)
                    first_letter = xl_col_to_name(0)
                    last_letter = xl_col_to_name(num_cols - 1)
                    
                    formula = f'TRIM(${fe_letter}2)="E"'
                    
                    if last_row > 1:
                        worksheet.conditional_format(
                            f'{first_letter}2:{last_letter}{last_row}',
                            {'type': 'formula', 'criteria': formula, 'format': light_blue_format}
                        )
                
                # Auto-fit columns
                max_width = EXCEL_FORMATTING["max_column_width"]
                for i, col_name in enumerate(df.columns):
                    col_data = df[col_name].astype(str)
                    max_len = col_data.map(len).max()
                    header_len = len(str(col_name))
                    width = max(max_len if pd.notna(max_len) else 0, header_len) + 2
                    width = min(width, max_width)
                    worksheet.set_column(i, i, width)
            
            logger.info(f"Saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Excel: {e}", exc_info=True)
            raise IOError(f"Lỗi khi lưu file Excel (có thể file đang được mở): {e}")
