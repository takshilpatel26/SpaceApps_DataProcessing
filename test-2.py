import os
from esa_snappy import ProductIO, GPF, HashMap, jpy
from datetime import datetime

# --- Constants from the Original Script ---
PRE_EVENT_SLC_ZIP = (
    "Inputs/pre_event/S1A_IW_SLC__1SDV_20240720T004052_20240720T004119_054837_06AD9C_26F2pre-event.zip"
)
POST_EVENT_SLC_ZIP = (
    "Inputs/post_event/S1A_IW_SLC__1SDV_20240801T004052_20240801T004119_055012_06B3B7_C85Dpost-event.zip"
)
OUTPUT_DIR = "SpaceApps_DataProcessing"
UTM_PROJECTION = "EPSG:32643"  # WGS 84 / UTM zone 43N

# --- Helper function to extract date from filename (as required by the handoff spec) ---
# --- Corrected Helper function to extract date from filename ---
def extract_date(zip_path):
    """
    Extracts the YYYY-MM-DD date string from the Sentinel-1 ZIP filename.
    The date is always the segment after T004...
    Example: S1A_IW_SLC__1SDV_20240720T004052...
    """
    import os
    from datetime import datetime

    # 1. Get just the filename from the path
    filename = os.path.basename(zip_path)

    # 2. Split the filename by the underscore '_'
    parts = filename.split('_')

    # The date is the fourth segment in a standard Sentinel-1 SLC name (YYYYMMDDT...)
    # We look for the 8-digit date followed by 'T'
    for part in parts:
        if len(part) >= 9 and part.startswith('2') and 'T' in part:
            # Extract the first 8 characters (YYYYMMDD)
            date_str = part[:8]
            try:
                # Format it to the required YYYY-MM-DD
                return datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
            except ValueError:
                # Continue searching if it's not a valid date
                continue

    # If the standard pattern fails, raise an error
    raise ValueError(f"Could not extract date from filename: {zip_path}")
# --- NEW FUNCTION: Generate Pre-processed Intensity Maps (Deliverable 1) ---
def generate_intensity_maps(input_zip_path, output_dir):
    """
    Performs the required pre-processing for Intensity Maps:
    1. TOPSAR-Split (for IW2)
    2. Apply-Orbit-File
    3. ThermalNoiseRemoval (optional, good practice for intensity)
    4. Calibration (Radiometric Calibration)
    5. TOPSAR-Deburst
    6. Multilooking (optional, helps with Speckle Filtering)
    7. Speckle Filtering
    8. Terrain Correction
    """
    print(f"--- Starting Intensity Map Generation for {os.path.basename(input_zip_path)} ---")

    date_str = extract_date(input_zip_path)
    product = ProductIO.readProduct(input_zip_path)

    # 1. TOPSAR-Split for subswath IW2 and both polarizations
    split_params = HashMap()
    split_params.put("subswath", "IW2")
    split_params.put("selectedPolarisations", "VV,VH")
    product = GPF.createProduct("TOPSAR-Split", split_params, product)

    # 2. Apply orbit files
    product = GPF.createProduct("Apply-Orbit-File", HashMap(), product)

    # 3. Thermal Noise Removal (Good practice)
    product = GPF.createProduct("ThermalNoiseRemoval", HashMap(), product)

    # 4. Calibration (Radiometric Calibration)
    calib_params = HashMap()
    # Output to Beta0 is common for this step, then converted to Sigma0 later
    calib_params.put("outputBetaBand", True)
    product = GPF.createProduct("Calibration", calib_params, product)

    # 5. TOPSAR-Deburst
    product = GPF.createProduct("TOPSAR-Deburst", HashMap(), product)
    # 6. Speckle Filtering (Fallback Fix)
    print(" -> Applying Speckle Filter...")

    # Get the Java Integer type
    java_int_type = jpy.get_type('java.lang.Integer')

    speckle_params = HashMap()
    speckle_params.put("filter", "Refined Lee")

    # FIX: Explicitly create a Java Integer object for the parameter values
    speckle_params.put("filterSizeX", java_int_type(5))
    speckle_params.put("filterSizeY", java_int_type(5))

    product = GPF.createProduct("Speckle-Filter", speckle_params, product)
    print(" -> Speckle Filter complete.")
    # 7. Terrain Correction (Corrections for geometric distortions)
    print(" -> Applying Terrain Correction and Final Output...")
    tc_params = HashMap()
    tc_params.put("demName", "SRTM 3Sec")
    tc_params.put("mapProjection", UTM_PROJECTION)
    tc_params.put("pixelSpacingInMeter", 10.0)
    product_final = GPF.createProduct("Terrain-Correction", tc_params, product)
    print(" -> Terrain Correction Applied.")

    # --- FIX START: Corrected dynamic band selection and saving ---

    all_band_names = list(product_final.getBandNames())
    vv_name = None
    vh_name = None

    # Search for the VV and VH intensity bands
    for name in all_band_names:
        if ('vv' in name.lower()) and ('beta0' in name.lower() or 'intensity' in name.lower()):
            vv_name = name
        elif ('vh' in name.lower()) and ('beta0' in name.lower() or 'intensity' in name.lower()):
            vh_name = name

    if vv_name is None or vh_name is None:
        raise RuntimeError(
            f"Could not find VV or VH intensity bands in the final product. Available bands: {all_band_names}")

    print(f" -> Found bands: VV='{vv_name}', VH='{vh_name}'")

    # 1. Save VV (Deliverable: YYYY-MM-DD_vv.tif)
    vv_select_params = HashMap()
    vv_select_params.put("sourceBands", jpy.array("java.lang.String", [vv_name]))

    vv_output_path = os.path.join(output_dir, f"{date_str}_vv.tif")
    vv_product = GPF.createProduct("BandSelect", vv_select_params, product_final)  # Use the pre-built HashMap
    ProductIO.writeProduct(vv_product, vv_output_path, "GeoTIFF")
    print(f"✅ Intensity Map VV successfully created: {vv_output_path}")

    # 2. Save VH (Deliverable: YYYY-MM-DD_vh.tif)
    vh_select_params = HashMap()
    vh_select_params.put("sourceBands", jpy.array("java.lang.String", [vh_name]))

    vh_output_path = os.path.join(output_dir, f"{date_str}_vh.tif")
    vh_product = GPF.createProduct("BandSelect", vh_select_params, product_final)  # Use the pre-built HashMap
    ProductIO.writeProduct(vh_product, vh_output_path, "GeoTIFF")
    print(f"✅ Intensity Map VH successfully created: {vh_output_path}")

    # --- FIX END ---

    return vv_output_path, vh_output_path


# --- MODIFIED FUNCTION: Generate Coherence Map (Deliverable 2) ---
def generate_coherence_map(master_zip_path, slave_zip_path, output_dir, polarization="VV"):
    print("--- Starting Coherence Map Generation (InSAR) ---")

    # Get dates for the file name specified in the handoff document: DATE1_DATE2_coherence.tif
    date1_str = extract_date(master_zip_path)
    date2_str = extract_date(slave_zip_path)
    coherence_filename = f"{date1_str}_{date2_str}_coherence.tif"

    # Read input products
    master = ProductIO.readProduct(master_zip_path)
    slave = ProductIO.readProduct(slave_zip_path)

    # Split subswath & polarization
    split_params = HashMap()
    split_params.put("subswath", "IW2")
    split_params.put("selectedPolarisations", polarization)
    master = GPF.createProduct("TOPSAR-Split", split_params, master)
    slave = GPF.createProduct("TOPSAR-Split", split_params, slave)

    # Apply orbit files
    master = GPF.createProduct("Apply-Orbit-File", HashMap(), master)
    slave = GPF.createProduct("Apply-Orbit-File", HashMap(), slave)

    # Back-geocoding (Coregistration of two SAR scenes)
    bg_params = HashMap()
    bg_params.put("demName", "SRTM 3Sec")
    bg_source_map = HashMap()
    bg_source_map.put("Master", master)
    bg_source_map.put("Slave", slave)
    product = GPF.createProduct("Back-Geocoding", bg_params, bg_source_map)
    print("Bands after Back-Geocoding:", list(product.getBandNames()))

    # Interferogram (interferogram formation and coherence estimation)
    product = GPF.createProduct("Interferogram", HashMap(), product)
    print("Bands after Interferogram:", list(product.getBandNames()))

    # Find coherence band dynamically
    band_names = list(product.getBandNames())
    coherence_band_name = None
    for b in band_names:
        if "coh" in b.lower():
            coherence_band_name = b
            break

    if coherence_band_name is None:
        raise RuntimeError("No coherence band found in product!")

    print(f" -> Selected Coherence Band: {coherence_band_name}")

    # Band selection
    band_select_params = HashMap()
    bands_to_select = jpy.array("java.lang.String", [coherence_band_name])
    band_select_params.put("sourceBands", bands_to_select)
    product_clean = GPF.createProduct("BandSelect", band_select_params, product)
    print(" -> BandSelect successful.")

    # Debursting
    print(" -> Debursting...")
    product_deburst = GPF.createProduct("TOPSAR-Deburst", HashMap(), product_clean)
    print(" -> Deburst complete.")

    # Terrain Correction
    print(" -> Applying Terrain Correction and Final Output...")
    tc_params = HashMap()
    tc_params.put("demName", "SRTM 3Sec")
    tc_params.put("mapProjection", UTM_PROJECTION)  # Using EPSG code
    product_final = GPF.createProduct("Terrain-Correction", tc_params, product_deburst)
    print(" -> Terrain Correction Applied.")

    # Save as GeoTIFF
    output_path = os.path.join(output_dir, coherence_filename)
    ProductIO.writeProduct(product_final, output_path, "GeoTIFF")

    print(f"✅ Coherence Map successfully created: {output_path}")
    return output_path


# --- Execution Block ---
if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # --- Step 1: Generate Pre-processed Intensity Maps (Deliverable 1) ---
    if os.path.exists(PRE_EVENT_SLC_ZIP):
        # Expected outputs: YYYY-MM-DD_vv.tif, YYYY-MM-DD_vh.tif
        generate_intensity_maps(PRE_EVENT_SLC_ZIP, OUTPUT_DIR)
    else:
        print(f"FATAL ERROR: Pre-event SLC ZIP file not found at {PRE_EVENT_SLC_ZIP}")

    if os.path.exists(POST_EVENT_SLC_ZIP):
        generate_intensity_maps(POST_EVENT_SLC_ZIP, OUTPUT_DIR)
    else:
        print(f"FATAL ERROR: Post-event SLC ZIP file not found at {POST_EVENT_SLC_ZIP}")

    # --- Step 2: Generate Coherence Map (Deliverable 2) ---
    if os.path.exists(PRE_EVENT_SLC_ZIP) and os.path.exists(POST_EVENT_SLC_ZIP):
        # Expected output: DATE1_DATE2_coherence.tif
        generate_coherence_map(PRE_EVENT_SLC_ZIP, POST_EVENT_SLC_ZIP, OUTPUT_DIR, "VV")
    else:
        print("FATAL ERROR: Cannot generate Coherence Map. Both SLC ZIP files are required.")