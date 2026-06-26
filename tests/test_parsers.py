import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parsers import (
    is_valid_container,
    MARINER_CONTAINER_DETAIL_PATTERN,
    PIONEER_CONTAINER_DETAIL_PATTERN,
    DANANG_CONTAINER_DETAIL_PATTERN,
    parse_weight_tons,
    parse_weight_kg
)

def test_is_valid_container():
    assert is_valid_container("ABCD1234567") is True
    assert is_valid_container("ABCD123") is False
    assert is_valid_container("ABC1234567") is False
    assert is_valid_container("abcd1234567") is True

def test_mariner_pattern():
    # MARINER: CONT_NO SEAL SIZE_TYPE DESCRIPTION WEIGHT_KGS
    line = "VNLU3097432 VMC134321 20DC GACH MEN 27,000"
    match = MARINER_CONTAINER_DETAIL_PATTERN.match(line)
    assert match is not None
    assert match.group("container_no") == "VNLU3097432"
    assert match.group("seal_no") == "VMC134321"
    assert match.group("size_type") == "20DC"
    assert match.group("description") == "GACH MEN"
    assert match.group("weight") == "27,000"

def test_pioneer_pattern():
    # PIONEER: CONT_NO SEAL SIZE_TYPE WEIGHT_TONS DESCRIPTION
    line = "CAIU6448632 A29395250 20GP 20 THEP DAY"
    match = PIONEER_CONTAINER_DETAIL_PATTERN.match(line)
    assert match is not None
    assert match.group("container_no") == "CAIU6448632"
    assert match.group("seal_no") == "A29395250"
    assert match.group("size_type") == "20GP"
    assert match.group("weight") == "20"
    assert match.group("description") == "THEP DAY"

def test_danang_pattern():
    # DANANG: CONT_NO SEAL SIZE_TYPE DESCRIPTION WEIGHT_KGS
    line = "VIMU6252197 A29005256 40HC VO LON 8000"
    match = DANANG_CONTAINER_DETAIL_PATTERN.match(line)
    assert match is not None
    assert match.group("container_no") == "VIMU6252197"
    assert match.group("seal_no") == "A29005256"
    assert match.group("size_type") == "40HC"
    assert match.group("description") == "VO LON"
    assert match.group("weight") == "8000"

def test_parse_weight_tons():
    assert parse_weight_tons("27,08") == 27.08
    assert parse_weight_tons("4") == 4.0
    assert parse_weight_tons("1,5") == 1.5
    assert parse_weight_tons("1,000") == 1.0

def test_parse_weight_kg():
    assert parse_weight_kg("27,000") == 27.0
    assert parse_weight_kg("8000") == 8.0
