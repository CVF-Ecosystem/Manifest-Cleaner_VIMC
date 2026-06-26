"""Regex patterns and parsing functions for VIMC Manifest Cleaner.

Supports two manifest formats:
1. MARINER type: Description first, weight in KGS
   Format: CONT_NO SEAL SIZE_TYPE DESCRIPTION WEIGHT_KGS
   
2. PIONEER/NAVIGATOR/STAR type: Weight first (TONS), then description
   Format: CONT_NO SEAL SIZE_TYPE WEIGHT_TONS DESCRIPTION
"""

from __future__ import annotations

import re
import logging
from typing import Optional, Dict, Any, Match

logger = logging.getLogger(__name__)

# Container number pattern: 4 letters + 4 to 7 digits (e.g., ABCD1234567, HCVT0001)
CONTAINER_PATTERN = re.compile(r'^[A-Z]{4}\d{4,7}$')

# MARINER type: Description first, then weight in KGS
# Example: VNLU3097432 VMC134321 20DC GẠCH MEN 27,000
MARINER_CONTAINER_DETAIL_PATTERN = re.compile(
    r"^(?P<container_no>[A-Z]{4}\d{4,7})\s+"          # Group 1: Container number
    r"(?:(?P<seal_no>[A-Z0-9]+)\s+)?"               # Group 2: Seal number (optional)
    r"(?P<size_type>[A-Z0-9\']{2,5})\s+"            # Group 3: Size/Type (20DC, 40HC, etc.)
    r"(?P<description>.+?)\s+"                      # Group 4: Description (non-greedy)
    r"(?P<weight>[\d\.,]+)\s*$",                    # Group 5: Weight in KGS
    re.IGNORECASE | re.UNICODE
)

# PIONEER/NAVIGATOR/STAR type: Weight first (TONS), then description
# Example: CAIU6448632 A29395250 20GP 20 THEP DAY
PIONEER_CONTAINER_DETAIL_PATTERN = re.compile(
    r"^(?P<container_no>[A-Z]{4}\d{4,7})\s+"          # Group 1: Container number
    r"(?:(?P<seal_no>.+?)\s+)?"                     # Group 2: Seal number (optional, non-greedy)
    r"(?P<size_type>[A-Z0-9\']{2,5})"               # Group 3: Size/Type
    r"(?=\s+[\d\.,])"                               # Lookahead for weight
    r"\s+(?P<weight>[\d\.,]+)\s+"                   # Group 4: Weight in TONS
    r"(?P<description>.+)$",                        # Group 5: Description
    re.IGNORECASE | re.UNICODE
)

# DANANG type: Description before weight (KGS at end), uses single spaces
# Example: VIMU6252197 A29005256 40HC VO LON 8000
# Pattern: CONT_NO SEAL SIZE_TYPE DESCRIPTION WEIGHT_KGS
DANANG_CONTAINER_DETAIL_PATTERN = re.compile(
    r"^(?P<container_no>[A-Z]{4}\d{4,7})\s+"          # Group 1: Container number
    r"(?P<seal_no>[A-Z0-9]+)\s+"                    # Group 2: Seal number (required)
    r"(?P<size_type>(?:20|40|45)(?:DC|GP|HC|HQ|TK|RF|RH|OT|FR))\s+"  # Group 3: Size/Type
    r"(?P<description>.+?)\s+"                      # Group 4: Description (non-greedy)
    r"(?P<weight>\d{3,})\s*$",                      # Group 5: Weight in KGS (3+ digits at end)
    re.IGNORECASE | re.UNICODE
)

# Pattern to extract container from MARKS & NUMBERS column
# Example: VNLU3097432/20DC or CAIU6448632 20GP
MARKS_CONTAINER_PATTERN = re.compile(
    r"([A-Z]{4}\d{4,7})"              # Group 1: Container number
    r"(?:[/\s]+([A-Z0-9\']+))?",    # Group 2: Size/Type (optional)
    re.IGNORECASE
)

# Stop keywords for party name extraction
STOP_KEYWORDS_PATTERN = re.compile(
    r'\b(ADD(?:RESS)?|TEL|FAX|EMAIL|PHONE|ADDRESS|MOBILE|CONTACT)\b',
    re.IGNORECASE | re.UNICODE
)

# Empty description pattern
EMPTY_DESC_PATTERN = re.compile(
    r'\b(EMPTY|CHUYEN RONG|CONTAINER RONG|CONT RONG|'
    r'CONT\.?\s*RONG|KHONG HANG|NO CARGO)\b',
    re.IGNORECASE | re.UNICODE
)


def is_valid_container(container_no: str) -> bool:
    """Check if string is a valid container number.
    
    Args:
        container_no: String to validate
        
    Returns:
        True if valid container number format
    """
    if not container_no:
        return False
    return bool(CONTAINER_PATTERN.match(container_no.strip().upper()))


def parse_container_line(line: str) -> Optional[str]:
    """Extract container number from a line if present.
    
    Args:
        line: Line of text to parse
        
    Returns:
        Container number if found, None otherwise
    """
    if not line:
        return None
    
    # Try to extract container number
    match = re.search(r'[A-Z]{4}\d{4,7}', line.upper())
    if match:
        return match.group(0)
    return None


def parse_mariner_container_detail(line: str) -> Optional[Dict[str, Any]]:
    """Parse container detail line in MARINER format.
    
    MARINER format: CONT_NO [SEAL] SIZE_TYPE DESCRIPTION WEIGHT_KGS
    
    Args:
        line: Line to parse
        
    Returns:
        Dictionary with container details or None if not matching
    """
    if not line or not line.strip():
        return None
    
    match = MARINER_CONTAINER_DETAIL_PATTERN.match(line.strip())
    if not match:
        return None
    
    return {
        "container_no": match.group("container_no").strip().upper(),
        "seal_no": match.group("seal_no").strip() if match.group("seal_no") else None,
        "size_type": match.group("size_type").strip().upper(),
        "description": match.group("description").strip(),
        "weight_raw": match.group("weight").strip(),
        "weight_unit": "KGS",
    }


def parse_pioneer_container_detail(line: str) -> Optional[Dict[str, Any]]:
    """Parse container detail line in PIONEER/NAVIGATOR/STAR format.
    
    PIONEER format: CONT_NO [SEAL] SIZE_TYPE WEIGHT_TONS DESCRIPTION
    
    Args:
        line: Line to parse
        
    Returns:
        Dictionary with container details or None if not matching
    """
    if not line or not line.strip():
        return None
    
    match = PIONEER_CONTAINER_DETAIL_PATTERN.match(line.strip())
    if not match:
        return None
    
    return {
        "container_no": match.group("container_no").strip().upper(),
        "seal_no": match.group("seal_no").strip() if match.group("seal_no") else None,
        "size_type": match.group("size_type").strip().upper(),
        "weight_raw": match.group("weight").strip(),
        "weight_unit": "TONS",
        "description": match.group("description").strip(),
    }


def parse_danang_container_detail(line: str) -> Optional[Dict[str, Any]]:
    """Parse container detail line in DANANG format.
    
    DANANG format: CONT_NO SEAL SIZE_TYPE DESCRIPTION WEIGHT_KGS
    Example: VIMU6252197 A29005256 40HC VO LON 8000
    
    Args:
        line: Line to parse
        
    Returns:
        Dictionary with container details or None if not matching
    """
    if not line or not line.strip():
        return None
    
    match = DANANG_CONTAINER_DETAIL_PATTERN.match(line.strip())
    if not match:
        return None
    
    return {
        "container_no": match.group("container_no").strip().upper(),
        "seal_no": match.group("seal_no").strip() if match.group("seal_no") else None,
        "size_type": match.group("size_type").strip().upper(),
        "description": match.group("description").strip(),
        "weight_raw": match.group("weight").strip(),
        "weight_unit": "KGS",
    }

def parse_marks_container(line: str) -> list[Dict[str, Any]]:
    """Extract container information from MARKS & NUMBERS column.
    
    Args:
        line: Line from MARKS & NUMBERS column
        
    Returns:
        List of dictionaries with container_no and size_type
    """
    results = []
    if not line:
        return results
    
    for match in MARKS_CONTAINER_PATTERN.finditer(line.strip()):
        container_no = match.group(1).strip().upper()
        size_type = match.group(2).strip().upper() if match.group(2) else None
        
        results.append({
            "container_no": container_no,
            "size_type": size_type,
        })
    
    return results


def parse_weight_kg(weight_str: str) -> Optional[float]:
    """Parse weight string in KGS format and convert to TONS.
    
    Args:
        weight_str: Weight string (e.g., "27,000" or "27000")
        
    Returns:
        Weight in TONS or None if parsing fails
    """
    if not weight_str:
        return None
    
    try:
        # Remove thousand separators
        cleaned = weight_str.replace(',', '').replace(' ', '')
        
        # Parse and convert to tons
        if '.' in cleaned:
            kg_value = float(cleaned)
        else:
            kg_value = int(cleaned)
        
        return kg_value / 1000.0
    
    except (ValueError, TypeError) as e:
        logger.warning(f"Cannot parse weight KGS: '{weight_str}' - {e}")
        return None


def parse_weight_tons(weight_str: str) -> Optional[float]:
    """Parse weight string already in TONS format.
    
    Args:
        weight_str: Weight string (e.g., "20" or "20.5")
        
    Returns:
        Weight in TONS or None if parsing fails
    """
    if not weight_str:
        return None
    
    try:
        # Handle comma as decimal separator
        cleaned = weight_str.replace(',', '.').strip()
        return float(cleaned)
    
    except (ValueError, TypeError) as e:
        logger.warning(f"Cannot parse weight TONS: '{weight_str}' - {e}")
        return None


def is_empty_description(description: str) -> bool:
    """Check if description indicates an empty container.
    
    Args:
        description: Description text
        
    Returns:
        True if description indicates empty container
    """
    if not description:
        return False
    return bool(EMPTY_DESC_PATTERN.search(description.upper()))


def clean_seal_number(seal: Optional[str]) -> Optional[str]:
    """Clean and validate seal number.
    
    Args:
        seal: Raw seal number
        
    Returns:
        Cleaned seal number or None if invalid
    """
    if not seal:
        return None
    
    cleaned = seal.strip().upper()
    
    # Check for N/A values
    if cleaned in ("N/A", "NA", "-", ""):
        return None
    
    return cleaned


def extract_bl_from_line(line: str, bl_identifier: str = "B/L NO:") -> Optional[str]:
    """Extract B/L number from a line containing B/L identifier.
    
    Args:
        line: Line potentially containing B/L number
        bl_identifier: Identifier to look for (default: "B/L NO:")
        
    Returns:
        B/L number or None if not found
    """
    if not line or bl_identifier.lower() not in line.lower():
        return None
    
    # Find position after identifier
    idx = line.lower().find(bl_identifier.lower())
    if idx == -1:
        return None
    
    # Extract text after identifier
    after_identifier = line[idx + len(bl_identifier):].strip()
    
    # Get first word as B/L number
    parts = after_identifier.split()
    if parts:
        return parts[0].strip()
    
    return None
