import os
from esa_snappy import ProductIO, GPF, HashMap, jpy
from datetime import datetime

# --- Constants (FIXED: Using raw strings 'r' for Windows paths) ---
PRE_EVENT_SLC_ZIP = (
    r"D:\Data Pre-Processing\SpaceApps_DataProcessing\Inputs\pre_event\S1A_IW_SLC__1SDV_20240720T004052_20240720T004119_054837_06AD9C_26F2pre-event.zip"
)
POST_EVENT_SLC_ZIP = (
    r"D:\Data Pre-Processing\SpaceApps_DataProcessing\Inputs\post_event\S1A_IW_SLC__1SDV_20240801T004052_20240801T004119_055012_06B3B7_C85Dpost-event.zip"
)
OUTPUT_DIR = "Output"
UTM_PROJECTION = "EPSG:32643"  # WGS 84 / UTM zone 43N


# --- FINAL, ROBUST Helper function to extract date from filename ---
def extract_date(zip_path):
    """
    Extracts the YYYY-MM-DD date string by searching for the YYYYMMDDT pattern,
    making it resilient to non-standard filename suffixes/segments.
    """
    import os
    from datetime import datetime

    filename = os.path.basename(zip_path)
    parts = filename.split('_')

    for part in parts:
        if len(part) >= 9 and part.startswith('2') and 'T' in part:
            date_str = part[:8]
            if date_str.isdigit():
                try:
                    return datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
                except ValueError:
                    continue

    raise ValueError(f"Could not extract date from filename: {zip_path}")


# --------------------------------------------------------------------------------------
# --- CORRECTED FUNCTION: Generate Pre-processed Intensity Maps (Stable Output) ---
# --------------------------------------------------------------------------------------
def generate_intensity_maps(input_zip_path, output_dir):
    print(f"--- Starting Intensity Map Generation for {os.path.basename(input_zip_path)} ---")

    date_str = extract_date(input_zip_path)

    # List to track all products for later cleanup
    products_to_close = []

    product = ProductIO.readProduct(input_zip_path)
    products_to_close.append(product)

    # 1. TOPSAR-Split
    split_params = HashMap()
    split_params.put("subswath", "IW2")
    split_params.put("selectedPolarisations", "VV,VH")
    product = GPF.createProduct("TOPSAR-Split", split_params, product)
    products_to_close.append(product)

    # 2. Apply orbit files
    product = GPF.createProduct("Apply-Orbit-File", HashMap(), product)
    products_to_close.append(product)

    # 3. Thermal Noise Removal
    product = GPF.createProduct("ThermalNoiseRemoval", HashMap(), product)
    products_to_close.append(product)

    # 4. Calibration (Output Beta0)
    calib_params = HashMap()
    calib_params.put("outputBetaBand", True)
    product = GPF.createProduct("Calibration", calib_params, product)
    products_to_close.append(product)

    # 5. TOPSAR-Deburst
    product_deburst = GPF.createProduct("TOPSAR-Deburst", HashMap(), product)
    products_to_close.append(product_deburst)

    # 6. Speckle Filtering
    print(" -> Applying Speckle Filter...")
    java_int_type = jpy.get_type('java.lang.Integer')
    speckle_params = HashMap()
    speckle_params.put("filter", "Refined Lee")
    speckle_params.put("filterSizeX", java_int_type(5))
    speckle_params.put("filterSizeY", java_int_type(5))
    product_filtered = GPF.createProduct("Speckle-Filter", speckle_params, product_deburst)
    products_to_close.append(product_filtered)
    print(" -> Speckle Filter complete.")

    # 7. Terrain Correction
    print(" -> Applying Terrain Correction and Final Output...")
    tc_params = HashMap()
    tc_params.put("demName", "SRTM 3Sec")
    tc_params.put("mapProjection", UTM_PROJECTION)
    tc_params.put("pixelSpacingInMeter", 10.0)
    product_tc = GPF.createProduct("Terrain-Correction", tc_params, product_filtered)
    products_to_close.append(product_tc)
    print(" -> Terrain Correction Applied.")

    # --- Final Output Preparation and Writing (Using Write Operator for Stability) ---
    all_band_names = list(product_tc.getBandNames())
    vv_name = None
    vh_name = None

    # FIX: Use Beta0 in the search since calibration was set to Beta0
    for name in all_band_names:
        if ('beta0' in name.lower() or 'intensity' in name.lower()) and ('vv' in name.lower()):
            vv_name = name
        elif ('beta0' in name.lower() or 'intensity' in name.lower()) and ('vh' in name.lower()):
            vh_name = name

    if vv_name is None or vh_name is None:
        raise RuntimeError(f"Could not find VV or VH bands in the final product.")

    print(f" -> Found bands: VV='{vv_name}', VH='{vh_name}'")

    # 1. WRITE VV BAND (Using the Write Operator)
    vv_output_path = os.path.join(output_dir, f"{date_str}_vv.tif")
    write_params_vv = HashMap()
    write_params_vv.put("formatName", "GeoTIFF")
    write_params_vv.put("file", vv_output_path)
    write_params_vv.put("sourceBands", jpy.array("java.lang.String", [vv_name]))

    GPF.createProduct("Write", write_params_vv, product_tc)
    print(f"✅ Intensity Map VV successfully created: {vv_output_path}")

    # 2. WRITE VH BAND (Using the Write Operator)
    vh_output_path = os.path.join(output_dir, f"{date_str}_vh.tif")
    write_params_vh = HashMap()
    write_params_vh.put("formatName", "GeoTIFF")
    write_params_vh.put("file", vh_output_path)
    write_params_vh.put("sourceBands", jpy.array("java.lang.String", [vh_name]))

    GPF.createProduct("Write", write_params_vh, product_tc)
    print(f"✅ Intensity Map VH successfully created: {vh_output_path}")

    # --- FINAL MEMORY CLEANUP ---
    for p in products_to_close:
        p.close()

    return vv_output_path, vh_output_path


# --------------------------------------------------------------------------------------
# --- CORRECTED FUNCTION: Generate Coherence Map (Delay Cleanup for Stability) ---
# --------------------------------------------------------------------------------------
def generate_coherence_map(master_zip_path, slave_zip_path, output_dir, polarization="VV"):
    print("--- Starting Coherence Map Generation (InSAR) ---")

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

    # Back-geocoding
    bg_params = HashMap()
    bg_params.put("demName", "SRTM 3Sec")
    bg_source_map = HashMap()
    bg_source_map.put("Master", master)
    bg_source_map.put("Slave", slave)
    product = GPF.createProduct("Back-Geocoding", bg_params, bg_source_map)
    print("Bands after Back-Geocoding:", list(product.getBandNames()))

    # Interferogram
    product = GPF.createProduct("Interferogram", HashMap(), product)
    print("Bands after Interferogram:", list(product.getBandNames()))

    # Find coherence band dynamically
    band_names = list(product.getBandNames())
    coherence_band_name = next((b for b in band_names if "coh" in b.lower()), None)
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

    # Terrain Correction (✅ use deburst product, not product_clean)
    print(" -> Applying Terrain Correction and Final Output...")
    tc_params = HashMap()
    tc_params.put("demName", "SRTM 3Sec")
    tc_params.put("mapProjection", UTM_PROJECTION)
    product_final = GPF.createProduct("Terrain-Correction", tc_params, product_deburst)
    print(" -> Terrain Correction Applied.")

    # Save as GeoTIFF using Write operator (more stable than ProductIO.writeProduct)
    output_path = os.path.join(OUTPUT_DIR, coherence_filename)
    write_params = HashMap()
    write_params.put("formatName", "GeoTIFF")
    write_params.put("file", output_path)
    write_params.put("sourceBands", jpy.array("java.lang.String", [coherence_band_name]))
    GPF.createProduct("Write", write_params, product_final)

    print(f"✅ Coherence Map successfully created: {output_path}")
    # --- FINAL MEMORY CLEANUP ---

    return output_path



# --- Execution Block ---
if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # --- Step 1: Generate Pre-processed Intensity Maps (Deliverable 1) ---
    if os.path.exists(PRE_EVENT_SLC_ZIP):
        generate_intensity_maps(PRE_EVENT_SLC_ZIP, OUTPUT_DIR)
    else:
        print(f"FATAL ERROR: Pre-event SLC ZIP file not found at {PRE_EVENT_SLC_ZIP}")

    if os.path.exists(POST_EVENT_SLC_ZIP):
        generate_intensity_maps(POST_EVENT_SLC_ZIP, OUTPUT_DIR)
    else:
        print(f"FATAL ERROR: Post-event SLC ZIP file not found at {POST_EVENT_SLC_ZIP}")

    # --- Step 2: Generate Coherence Map (Deliverable 2) ---
    if os.path.exists(PRE_EVENT_SLC_ZIP) and os.path.exists(POST_EVENT_SLC_ZIP):
        generate_coherence_map(PRE_EVENT_SLC_ZIP, POST_EVENT_SLC_ZIP, OUTPUT_DIR, "VV")
    else:
        print("FATAL ERROR: Cannot generate Coherence Map. Both SLC ZIP files are required.")