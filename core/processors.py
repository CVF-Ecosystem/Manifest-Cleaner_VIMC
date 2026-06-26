"""Processing logic for VIMC Manifest Cleaner.

Contains functions for determining F/E status, cargo type, and cleaning party names.
"""

from __future__ import annotations

import re
import logging
from typing import Optional, Dict, Any

from config.mappings import SIZE_TO_ISO, CARGO_TYPE_MAPPING, SIZE_TO_VTOS
from config.constants import (
    FE_THRESHOLDS,
    SOC_KEYWORDS,
    COC_KEYWORDS,
    EMPTY_KEYWORDS,
)
from core.parsers import STOP_KEYWORDS_PATTERN, EMPTY_DESC_PATTERN

logger = logging.getLogger(__name__)


# Pattern to match cargo item with quantity and container type
# Example: "GACH MEN (01) x20'DC COC" -> ("GACH MEN", 1, "20DC")
CARGO_QTY_PATTERN = re.compile(
    r"([A-Za-zÀ-ỹ\s\-/\.()]+?)"  # Cargo name (including Vietnamese chars)
    r"\s*\((\d+)\)\s*"           # Quantity in parentheses like (01)
    r"x\s*(\d{2})'?([A-Z0-9]{1,4})"  # Container type: xNN'XX or xNNXX
    r"\s*(?:COC|SOC)?",           # Optional COC/SOC marker
    re.IGNORECASE | re.UNICODE
)


def get_iso_size(size_type: Optional[str]) -> Optional[str]:
    """Get ISO code for container size/type.
    
    Args:
        size_type: Container size/type (e.g., "20DC", "40HC")
        
    Returns:
        ISO code or None if not found
    """
    if not size_type:
        return None
    
    normalized = size_type.upper().replace("'", "").strip()
    iso = SIZE_TO_ISO.get(normalized)
    
    
    if not iso:
        logger.debug(f"No ISO mapping found for size_type: '{size_type}'")
    
    return iso


def get_vtos_size(size_type: Optional[str]) -> Optional[str]:
    """Convert size/type to VTOS standard format.
    
    Args:
        size_type: Container size/type code (e.g., "40GP", "20RF")
        
    Returns:
        VTOS standardized code, or original if no mapping exists.
    """
    if not size_type:
        return None
    st = str(size_type).upper().strip()
    return SIZE_TO_VTOS.get(st, st)


def determine_fe(
    description: Optional[str],
    weight_info: Optional[Dict[str, Any]],
    size_type: Optional[str],
    is_explicitly_empty: bool = False
) -> str:
    """Determine Full/Empty status of container.
    
    Args:
        description: Cargo description
        weight_info: Dictionary with 'value' (float, tons) and 'unit' keys
        size_type: Container size/type
        is_explicitly_empty: Whether container is marked as empty
        
    Returns:
        'F' for Full or 'E' for Empty
    """
    # Explicitly marked as empty
    if is_explicitly_empty:
        logger.debug(f"Container {size_type or 'N/A'} marked E (explicit empty flag)")
        return 'E'
    
    # Get thresholds
    tare_40ft = FE_THRESHOLDS.get("tare_40ft", 5.0)
    tare_20ft = FE_THRESHOLDS.get("tare_20ft", 3.0)
    tare_40rf = FE_THRESHOLDS.get("tare_40rf", 4.8)
    tare_20rf = FE_THRESHOLDS.get("tare_20rf", 3.0)
    cargo_weight_empty = FE_THRESHOLDS.get("cargo_weight_empty", 0.05)
    
    # Check description for empty keywords
    if description and EMPTY_DESC_PATTERN.search(description.upper()):
        logger.debug(f"Container {size_type or 'N/A'} marked E (empty description)")
        return 'E'
    
    # Check weight
    if weight_info and weight_info.get('value') is not None:
        weight = weight_info['value']
        
        # Very low weight = empty
        if weight <= cargo_weight_empty:
            logger.debug(f"Container {size_type or 'N/A'} weight {weight}T <= {cargo_weight_empty}T. Marked E.")
            return 'E'
        
        # Check against tare weight thresholds
        if size_type:
            normalized_type = size_type.upper().strip()
            
            # Reefer containers have higher tare weights
            if normalized_type.endswith("RF") or "RF" in normalized_type:
                if normalized_type.startswith('4'):
                    if weight <= tare_40rf:
                        logger.debug(f"Container {size_type} weight {weight}T <= RF tare {tare_40rf}T. Marked E.")
                        return 'E'
                elif normalized_type.startswith('2'):
                    if weight <= tare_20rf:
                        logger.debug(f"Container {size_type} weight {weight}T <= RF tare {tare_20rf}T. Marked E.")
                        return 'E'
            
            # Standard containers
            if normalized_type.startswith('4'):
                if weight <= tare_40ft:
                    logger.debug(f"Container {size_type} weight {weight}T <= tare {tare_40ft}T. Marked E.")
                    return 'E'
            elif normalized_type.startswith('2'):
                if weight <= tare_20ft:
                    logger.debug(f"Container {size_type} weight {weight}T <= tare {tare_20ft}T. Marked E.")
                    return 'E'
    
    return 'F'


def determine_cargo_type(size_type: Optional[str], fe_status: str) -> str:
    """Determine cargo type based on container type and F/E status.
    
    Args:
        size_type: Container size/type
        fe_status: 'F' or 'E'
        
    Returns:
        Cargo type string (e.g., "GENERAL", "EMPTY", "EMPTY REEFER")
    """
    if not size_type:
        return "UNKNOWN"
    
    normalized = size_type.upper().replace("'", "").strip()
    
    # First try direct mapping
    base_type = CARGO_TYPE_MAPPING.get(normalized)
    
    # If not found, try ISO code
    if not base_type:
        iso_code = get_iso_size(size_type)
        if iso_code:
            base_type = CARGO_TYPE_MAPPING.get(iso_code, "GENERAL")
        else:
            base_type = "GENERAL"
    
    # Apply F/E status
    if fe_status == 'E':
        if base_type == "GENERAL":
            return "EMPTY"
        else:
            return f"EMPTY {base_type}"
    
    return base_type


def determine_operator(
    description_text: str,
    default_operator: str = "VMC",
    soc_code: str = "SVM",
    coc_code: str = "VMC"
) -> tuple[str, bool]:
    """Determine operator (SOC/COC) from description text.
    
    Args:
        description_text: Full description text to check
        default_operator: Default operator if not determined
        soc_code: SOC operator code
        coc_code: COC operator code
        
    Returns:
        Tuple of (operator_code, is_soc)
    """
    if not description_text:
        return coc_code, False
    
    text_upper = " ".join(description_text.upper().split())
    
    # Check for SOC keywords first (priority)
    for kw in SOC_KEYWORDS:
        if kw in text_upper:
            logger.debug(f"Found SOC keyword '{kw}' in description")
            return soc_code, True
    
    # Check for COC keywords
    for kw in COC_KEYWORDS:
        if kw in text_upper:
            logger.debug(f"Found COC keyword '{kw}' in description")
            return coc_code, False
    
    # Default to COC
    return coc_code, False


def is_empty_bl(description_text: str) -> bool:
    """Check if B/L contains empty containers based on description.
    
    Args:
        description_text: Full description text
        
    Returns:
        True if contains empty indicators
    """
    if not description_text:
        return False
    
    text_upper = description_text.upper()
    
    # Check specific empty keywords
    for kw in EMPTY_KEYWORDS:
        if kw in text_upper:
            return True
    
    # Check SOC EMPTY specifically
    if "SOC EMPTY" in text_upper:
        return True
    
    return bool(EMPTY_DESC_PATTERN.search(text_upper))


def clean_party_name(full_party_text: str) -> str:
    """Clean party name (shipper/consignee/notify).
    
    Extracts first line and removes stop keywords.
    
    Args:
        full_party_text: Full party information text
        
    Returns:
        Cleaned party name
    """
    if not full_party_text or full_party_text != full_party_text:  # Check for NaN
        return ""
    
    # Get first line
    first_line = full_party_text.split('\n')[0].strip()
    
    # Remove party markers (1), 2), 3))
    if first_line.startswith(("1)", "2)", "3)")):
        first_line = first_line[2:].lstrip()
    
    # Find stop keyword position
    if STOP_KEYWORDS_PATTERN:
        match = STOP_KEYWORDS_PATTERN.search(first_line)
        if match:
            first_line = first_line[:match.start()].strip()
    
    # Clean trailing punctuation
    return first_line.rstrip(';,/\\- ')


def refine_description_column(
    description: str,
    fe_status: str,
    cargo_type: str
) -> str:
    """Refine description based on F/E status and cargo type.
    
    Args:
        description: Original description
        fe_status: 'F' or 'E'
        cargo_type: Determined cargo type
        
    Returns:
        Refined description
    """
    if fe_status == 'E':
        if cargo_type == "EMPTY" or cargo_type.startswith("EMPTY "):
            return "EMPTY"
    
    return description.strip() if description else ""


def validate_seal_number(seal: Optional[str]) -> bool:
    """Validate if seal number format is correct.
    
    Valid seal: 6 or 7 digits only
    
    Args:
        seal: Seal number to validate
        
    Returns:
        True if valid format
    """
    if not seal:
        return True  # Empty is valid (no seal)
    
    cleaned = seal.strip()
    if not cleaned:
        return True
    
    # Check if it's numeric and 6-7 digits
    if cleaned.isdigit() and len(cleaned) in (6, 7):
        return True
    
    return False


def parse_cargo_items_with_qty(description: str) -> list:
    """Parse cargo description to extract items with quantities and container types.
    
    Args:
        description: Raw description like "GACH MEN (01) x20'DC COC, PHAN BON (01) x20'DC COC"
        
    Returns:
        List of tuples: (cargo_name, quantity, container_type)
    """
    if not description:
        return []
    
    desc_str = str(description).strip()
    items = []
    
    for match in CARGO_QTY_PATTERN.finditer(desc_str):
        cargo_name = match.group(1).strip()
        qty = int(match.group(2))
        size_prefix = match.group(3)
        size_suffix = match.group(4).upper()
        container_type = f"{size_prefix}{size_suffix}"
        
        if cargo_name:
            items.append((cargo_name, qty, container_type))
    
    return items


def match_description_by_quantity(
    containers: list,
    description: str
) -> list:
    """Match cargo descriptions to containers based on quantity and order.
    
    When a manifest line has multiple cargo items with quantities like:
    "GACH MEN (01) x20'DC COC, PHAN BON (01) x20'DC COC"
    
    This function assigns each cargo to containers in order.
    
    Args:
        containers: List of container dicts with 'Size_Type' key
        description: Raw description text
        
    Returns:
        List of descriptions matched to each container in order
    """
    if not containers:
        return []
    
    n = len(containers)
    result = [""] * n
    
    cargo_items = parse_cargo_items_with_qty(description)
    
    if not cargo_items:
        # No quantity info - return original for all
        return [description.strip() if description else ""] * n
    
    # Group containers by type with their indices
    type_to_indices = {}
    for i, cont in enumerate(containers):
        cont_type = str(cont.get("Size_Type") or cont.get("size_type") or "").upper().replace("'", "")
        if cont_type not in type_to_indices:
            type_to_indices[cont_type] = []
        type_to_indices[cont_type].append(i)
    
    # Track assignment position for each container type
    type_assign_pos = {t: 0 for t in type_to_indices}
    
    # Assign cargo to containers in order
    for cargo_name, qty, cont_type in cargo_items:
        cont_type_upper = cont_type.upper().replace("'", "")
        if cont_type_upper not in type_to_indices:
            continue
        
        indices = type_to_indices[cont_type_upper]
        start_pos = type_assign_pos[cont_type_upper]
        
        for _ in range(qty):
            if start_pos >= len(indices):
                break
            idx = indices[start_pos]
            if not result[idx]:
                result[idx] = cargo_name
            start_pos += 1
        
        type_assign_pos[cont_type_upper] = start_pos
    
    # Fill remaining with original description
    for i, desc in enumerate(result):
        if not desc:
            result[i] = description.strip() if description else ""
    
    return result
