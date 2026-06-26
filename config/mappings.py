"""Mappings for VIMC Manifest Cleaner.

Contains size to ISO mappings and cargo type mappings.
"""

from typing import Dict

# Size to ISO code mapping
SIZE_TO_ISO: Dict[str, str] = {
    # 20ft containers
    "20DC": "22G1",
    "20GP": "22G1",
    "20'DC": "22G1",
    "20'GP": "22G1",
    "20DV": "22G1",
    "20HC": "25G1",
    "20OT": "22U1",
    "20FR": "22P1",
    "20RF": "22R1",
    "20TK": "22T1",
    "20PF": "22P3",
    "20BK": "22B0",
    
    # 40ft containers
    "40DC": "42G1",
    "40GP": "42G1",
    "40'DC": "42G1",
    "40'GP": "42G1",
    "40DV": "42G1",
    "40HC": "45G1",
    "40HQ": "45G1",
    "40'HC": "45G1",
    "40'HQ": "45G1",
    "40OT": "42U1",
    "40FR": "42P1",
    "40RF": "42R1",
    "40RH": "45R1",
    "40TK": "42T1",
    "40PF": "42P3",
    "40BK": "42B0",
    "40NOR": "42G0",
    
    # 45ft containers
    "45HC": "L5G1",
    "45HQ": "L5G1",
    "45'HC": "L5G1",
    "45'HQ": "L5G1",
    "45RF": "L5R1",
    "45GP": "L5G1",
    
    # Direct ISO codes
    "22G1": "22G1",
    "22G0": "22G0",
    "22U1": "22U1",
    "22P1": "22P1",
    "22R1": "22R1",
    "22T1": "22T1",
    "25G1": "25G1",
    "42G1": "42G1",
    "42G0": "42G0",
    "42U1": "42U1",
    "42P1": "42P1",
    "42R1": "42R1",
    "45G1": "45G1",
    "45R1": "45R1",
    "L5G1": "L5G1",
    "L5R1": "L5R1",
}

# Cargo type base mapping based on container type
CARGO_TYPE_MAPPING: Dict[str, str] = {
    # General purpose
    "22G1": "GENERAL",
    "22G0": "GENERAL",
    "42G1": "GENERAL",
    "42G0": "GENERAL",
    "45G1": "GENERAL",
    "L5G1": "GENERAL",
    "25G1": "GENERAL",
    
    # Reefer
    "22R1": "REEFER",
    "42R1": "REEFER",
    "45R1": "REEFER",
    "L5R1": "REEFER",
    
    # Open Top
    "22U1": "OPEN TOP",
    "42U1": "OPEN TOP",
    
    # Flat Rack
    "22P1": "FLAT RACK",
    "22P3": "FLAT RACK",
    "42P1": "FLAT RACK",
    "42P3": "FLAT RACK",
    
    # Tank
    "22T1": "GENERAL",
    "42T1": "GENERAL",
    
    # Bulk
    "22B0": "BULK",
    "42B0": "BULK",
    
    # Size type direct mapping
    "20DC": "GENERAL",
    "20GP": "GENERAL",
    "20HC": "GENERAL",
    "20RF": "REEFER",
    "20OT": "OPEN TOP",
    "20FR": "FLAT RACK",
    "20TK": "GENERAL",
    "40DC": "GENERAL",
    "40GP": "GENERAL",
    "40HC": "GENERAL",
    "40HQ": "GENERAL",
    "40RF": "REEFER",
    "40RH": "REEFER",
    "40OT": "OPEN TOP",
    "40FR": "FLAT RACK",
    "40TK": "GENERAL",
    "45HC": "GENERAL",
    "45HQ": "GENERAL",
    "45RF": "REEFER",
}

# VIMC B/L identifier
BL_NO_IDENTIFIER = "B/L NO:"

# Party markers for VIMC format
PARTY_MARKERS = {
    "shipper": "1)",
    "consignee": "2)",
    "notify": "3)",
}

# --- Mapping: Size/Type -> VTOS ---
# Converts various container size codes to standardized VTOS format.
SIZE_TO_VTOS: Dict[str, str] = {
    # Standard Dry Containers
    "20DC": "20DC",
    "20GP": "20DC",
    "40DC": "40DC",
    "40GP": "40HC",
    "40HC": "40HC",
    "45GP": "45HC",
    "45HC": "45HC",
    
    # ISO Codes Mapping
    "22G1": "20DC",
    "42G1": "40DC",
    "45G1": "40HC",
    "45R1": "45RH", # Or check standard
    "22R1": "22R0",
    "25G1": "20HC", # 20 High Cube?
    "42R1": "40RH",
    
    # Reefer Containers
    "20RF": "22R0",
    "40RF": "40RH",
    "45RF": "45RH",
    "20RH": "22R0",
    "40RH": "40RH",
    "45RH": "45RH",
    
    # Tank Containers
    "20TK": "20TK",
    
    # Flat Rack Containers
    "20FR": "20FL",
    "40FR": "40FL",
    
    # Open Top Containers
    "20OT": "20OT",
    "40OT": "40OT",
}
