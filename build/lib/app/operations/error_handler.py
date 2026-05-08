def translate_sap_error(error_text: str) -> str:
    if "Business Partner not found" in error_text:
        return "Vendor not found in SAP. Please provide a valid CardCode."
    if "Item not found" in error_text:
        return "Item not found in SAP. Please provide a valid ItemCode."
    if "Vendor not found" in error_text:
        return "Vendor not found in SAP. Please provide a valid vendor CardCode."
    return f"SAP Error: {error_text}"
