import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.processors import determine_fe, get_iso_size

def test_get_iso_size():
    assert get_iso_size("20DC") == "22G1"
    assert get_iso_size("40HC") == "45G1"
    assert get_iso_size("45HC") == "L5G1"
    assert get_iso_size("UNKNOWN") is None

def test_determine_fe():
    # 20ft container max tare is around 2.5
    assert determine_fe(description="EMPTY", weight_info={'value': 0.0}, size_type="20DC") == "E"
    assert determine_fe(description="", weight_info={'value': 2.0}, size_type="20DC") == "E"
    assert determine_fe(description="", weight_info={'value': 5.0}, size_type="20DC") == "F"
    
    # 40ft container max tare is around 4.5
    assert determine_fe(description="", weight_info={'value': 3.5}, size_type="40HC") == "E"
    assert determine_fe(description="", weight_info={'value': 5.5}, size_type="40HC") == "F"
    
    # Reefers
    assert determine_fe(description="", weight_info={'value': 4.0}, size_type="40RH") == "E"
    assert determine_fe(description="", weight_info={'value': 6.0}, size_type="40RH") == "F"

    # Explicit empty
    assert determine_fe(description="EMPTY", weight_info={'value': 20.0}, size_type="20DC", is_explicitly_empty=True) == "E"
