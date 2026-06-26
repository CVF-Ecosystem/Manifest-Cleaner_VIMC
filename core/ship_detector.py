"""Ship type detection for VIMC Manifest Cleaner.

Auto-detects ship type (MARINER vs PIONEER/NAVIGATOR/STAR) from filename.
"""

from __future__ import annotations

import logging
from pathlib import Path
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ShipType(Enum):
    """Ship type enumeration."""
    MARINER = "mariner"           # Description first, weight in KGS
    PIONEER = "pioneer"           # Weight first (TONS), then description
    UNKNOWN = "unknown"


# Keywords for ship type detection
MARINER_KEYWORDS = ["MARINER"]
PIONEER_TYPE_KEYWORDS = ["PIONEER", "NAVIGATOR", "STAR"]


def detect_ship_type(file_path: str | Path) -> ShipType:
    """Detect ship type from filename or file content.
    
    Ship type determines the manifest format:
    - MARINER: Description first, weight in KGS
    - PIONEER/NAVIGATOR/STAR: Weight first (TONS), then description
    
    Detection priority:
    1. Check filename for keywords
    2. Read file content for VESSEL name
    
    Args:
        file_path: Path to manifest file
        
    Returns:
        Detected ShipType enum value
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    filename_upper = file_path.name.upper()
    
    # First: Check filename for keywords
    for keyword in MARINER_KEYWORDS:
        if keyword in filename_upper:
            logger.info(f"Detected ship type: MARINER from filename '{file_path.name}'")
            return ShipType.MARINER
    
    for keyword in PIONEER_TYPE_KEYWORDS:
        if keyword in filename_upper:
            logger.info(f"Detected ship type: PIONEER (keyword: {keyword}) from filename '{file_path.name}'")
            return ShipType.PIONEER
    
    # Second: Read file content to find VESSEL name
    try:
        ship_type = _detect_from_content(file_path)
        if ship_type != ShipType.UNKNOWN:
            logger.info(f"Detected ship type: {ship_type.value} from file content")
            return ship_type
    except Exception as e:
        logger.warning(f"Could not read file content for ship detection: {e}")
    
    # Fallback: Check for generic VIMC - default to PIONEER (most common)
    if "VIMC" in filename_upper or "MNF" in filename_upper:
        logger.info(f"Detected VIMC/MNF file, defaulting to PIONEER type for '{file_path.name}'")
        return ShipType.PIONEER
    
    logger.warning(f"Could not detect ship type from filename '{file_path.name}'")
    return ShipType.UNKNOWN


def _detect_from_content(file_path: Path) -> ShipType:
    """Detect ship type by reading VESSEL name from file content.
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Detected ShipType or UNKNOWN
    """
    import pandas as pd
    
    # Determine engine
    engine = 'openpyxl' if file_path.suffix.lower() == '.xlsx' else 'xlrd'
    
    try:
        # Read first 20 rows to find VESSEL info
        df_peek = pd.read_excel(
            file_path,
            sheet_name=0,
            header=None,
            nrows=20,
            keep_default_na=False,
            engine=engine
        )
    except Exception:
        # Try with default engine
        df_peek = pd.read_excel(
            file_path,
            sheet_name=0,
            header=None,
            nrows=20,
            keep_default_na=False
        )
    
    # Search for VESSEL keyword and extract ship name
    for idx, row in df_peek.iterrows():
        for cell in row:
            cell_str = str(cell).upper()
            if "VESSEL" in cell_str:
                # Check the whole row for ship keywords
                row_text = " ".join(str(c).upper() for c in row)
                
                for keyword in MARINER_KEYWORDS:
                    if keyword in row_text:
                        return ShipType.MARINER
                
                for keyword in PIONEER_TYPE_KEYWORDS:
                    if keyword in row_text:
                        return ShipType.PIONEER
    
    return ShipType.UNKNOWN


def get_ship_type_display_name(ship_type: ShipType, lang: str = "vi") -> str:
    """Get display name for ship type.
    
    Args:
        ship_type: ShipType enum value
        lang: Language code ('vi' or 'en')
        
    Returns:
        Display name string
    """
    names = {
        ShipType.MARINER: {
            "vi": "🚢 MARINER",
            "en": "🚢 MARINER",
        },
        ShipType.PIONEER: {
            "vi": "🚢 PIONEER/NAVIGATOR/STAR",
            "en": "🚢 PIONEER/NAVIGATOR/STAR",
        },
        ShipType.UNKNOWN: {
            "vi": "❓ Chưa xác định",
            "en": "❓ Unknown",
        },
    }
    
    return names.get(ship_type, {}).get(lang, str(ship_type.value))


def get_ship_type_color(ship_type: ShipType) -> str:
    """Get color for ship type indicator.
    
    Args:
        ship_type: ShipType enum value
        
    Returns:
        Color hex code
    """
    colors = {
        ShipType.MARINER: "#1D70B8",   # Modern Blue
        ShipType.PIONEER: "#10B981",   # Modern Emerald Green
        ShipType.UNKNOWN: "#64748B",   # Slate Gray
    }
    
    return colors.get(ship_type, "#64748B")


def get_ship_type_description(ship_type: ShipType, lang: str = "vi") -> str:
    """Get detailed description of ship type format.
    
    Args:
        ship_type: ShipType enum value
        lang: Language code
        
    Returns:
        Description string
    """
    descriptions = {
        ShipType.MARINER: {
            "vi": "Format: CONT SEAL TYPE MÔ_TẢ TRỌNG_LƯỢNG(KGS)",
            "en": "Format: CONT SEAL TYPE DESCRIPTION WEIGHT(KGS)",
        },
        ShipType.PIONEER: {
            "vi": "Format: CONT SEAL TYPE TRỌNG_LƯỢNG(TẤN) MÔ_TẢ",
            "en": "Format: CONT SEAL TYPE WEIGHT(TONS) DESCRIPTION",
        },
        ShipType.UNKNOWN: {
            "vi": "Chưa xác định định dạng manifest",
            "en": "Manifest format unknown",
        },
    }
    
    return descriptions.get(ship_type, {}).get(lang, "")


def is_mariner_type(ship_type: ShipType) -> bool:
    """Check if ship type is MARINER format.
    
    Args:
        ship_type: ShipType enum value
        
    Returns:
        True if MARINER type
    """
    return ship_type == ShipType.MARINER


def is_pioneer_type(ship_type: ShipType) -> bool:
    """Check if ship type is PIONEER format (includes NAVIGATOR, STAR).
    
    Args:
        ship_type: ShipType enum value
        
    Returns:
        True if PIONEER type
    """
    return ship_type == ShipType.PIONEER
