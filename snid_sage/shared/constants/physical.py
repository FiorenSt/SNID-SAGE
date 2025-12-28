"""
SNID-SAGE – Physical & Astronomical Constants
=============================================

Air and vacuum wavelengths for every emission/absorption line used in the
SNID-SAGE analysis suite (super-novae, stellar, host-galaxy).

The canonical line list is now packaged as JSON at `snid_sage/lines/line_database.json`
and loaded at runtime. Helpers and color/category mappings remain here for
compatibility with existing code.
"""

# ---------------------------------------------------------------------------
# Universal physical constants
# ---------------------------------------------------------------------------
SPEED_OF_LIGHT          = 299_792_458        # m s⁻¹
SPEED_OF_LIGHT_KMS      = 299_792.458        # km s⁻¹

# ---------------------------------------------------------------------------
# Handy top-level constants for a few "classics"
# Backwards compatibility with older scripts
# ---------------------------------------------------------------------------
# Balmer
HYDROGEN_ALPHA          = 6562.80   # air wavelength
HYDROGEN_BETA           = 4861.36
HYDROGEN_GAMMA          = 4340.47
HYDROGEN_DELTA          = 4101.74
# He I
HELIUM_I_5876           = 5875.67
HELIUM_I_6678           = 6678.15
HELIUM_I_7065           = 7065.15
# Ca II H&K
CALCIUM_II_H            = 3968.47
CALCIUM_II_K            = 3933.67

# ---------------------------------------------------------------------------
# Full spectral-line catalogue (loaded from packaged JSON)
# ---------------------------------------------------------------------------
# A single table drives every downstream tool.
# Each entry fields: key, wavelength_vacuum, wavelength_air, sn_types, category, origin, note

from snid_sage.shared.utils.line_detection.line_db_loader import (
    get_all_lines as _load_all_lines,
    get_categories as _load_categories,
)

LINE_DB = [
    {"key":"H-alpha", "wavelength_vacuum":6564.61, "wavelength_air":6562.80, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen", "origin":"sn"},
    {"key":"H-beta", "wavelength_vacuum":4862.72, "wavelength_air":4861.36, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen", "origin":"sn"},
    {"key":"H-gamma", "wavelength_vacuum":4341.69, "wavelength_air":4340.47, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen", "origin":"sn"},
    {"key":"H-delta", "wavelength_vacuum":4102.90, "wavelength_air":4101.74, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen", "origin":"sn"},
    {"key":"H-epsilon", "wavelength_vacuum":3970.07, "wavelength_air":3968.95, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen", "origin":"sn"},
    {"key":"H8", "wavelength_vacuum":3889.05, "wavelength_air":3887.95, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen", "origin":"sn"},
    {"key":"Pa-beta", "wavelength_vacuum":12818.10, "wavelength_air":12814.59, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen_nir", "origin":"sn"},
    {"key":"Pa-alpha", "wavelength_vacuum":18751.00, "wavelength_air":18745.88, "sn_types":["II", "IIn", "IIb"], "category":"hydrogen_nir", "origin":"sn"},
    {"key":"He I 4471", "wavelength_vacuum":4472.70, "wavelength_air":4471.45, "sn_types":["Ib", "IIb"], "category":"helium", "origin":"sn"},
    {"key":"He I 5876", "wavelength_vacuum":5877.30, "wavelength_air":5875.67, "sn_types":["Ib", "IIb"], "category":"helium", "origin":"sn"},
    {"key":"He I 6678", "wavelength_vacuum":6679.99, "wavelength_air":6678.15, "sn_types":["Ib", "IIb"], "category":"helium", "origin":"sn"},
    {"key":"He I 7065", "wavelength_vacuum":7067.10, "wavelength_air":7065.15, "sn_types":["Ib", "IIb"], "category":"helium", "origin":"sn"},
    {"key":"He I 7281", "wavelength_vacuum":7283.40, "wavelength_air":7281.39, "sn_types":["Ib", "IIb"], "category":"helium", "origin":"sn"},
    {"key":"He I 10830", "wavelength_vacuum":10833.30, "wavelength_air":10830.33, "sn_types":["Ib", "IIb"], "category":"helium", "origin":"sn"},

    {"key":"C II 6578", "wavelength_vacuum":6579.90, "wavelength_air":6578.08, "sn_types":["Ia", "Ic"], "category":"carbon", "origin":"sn"},
    {"key":"C II 6583", "wavelength_vacuum":6584.70, "wavelength_air":6582.88, "sn_types":["Ia", "Ic"], "category":"carbon", "origin":"sn"},
    {"key":"C II 7234", "wavelength_vacuum":7233.30, "wavelength_air":7231.31, "sn_types":["Ia", "Ic"], "category":"carbon", "origin":"sn"},
    {"key":"C II 7238", "wavelength_vacuum":7238.40, "wavelength_air":7236.41, "sn_types":["Ia", "Ic"], "category":"carbon", "origin":"sn"},
    {"key":"C II 4267", "wavelength_vacuum":4268.40, "wavelength_air":4267.20, "sn_types":["Ia", "Ib"], "category":"carbon", "origin":"sn"},
    {"key":"[C I] 8727", "wavelength_vacuum":8729.10, "wavelength_air":8726.70, "sn_types":["II", "Ib", "Ic"], "category":"carbon", "origin":"sn"},
    {"key":"[N II] 5755", "wavelength_vacuum":5756.20, "wavelength_air":5754.60, "sn_types":["Ib", "IIn"], "category":"nitrogen", "origin":"sn"},
    {"key":"[N II] 6549", "wavelength_vacuum":6549.90, "wavelength_air":6548.09, "sn_types":["Ib", "IIn"], "category":"nitrogen", "origin":"sn"},
    {"key":"[N II] 6585", "wavelength_vacuum":6585.30, "wavelength_air":6583.48, "sn_types":["Ib", "IIn"], "category":"nitrogen", "origin":"sn"},
    {"key":"O I 7774", "wavelength_vacuum":7775.00, "wavelength_air":7772.86, "sn_types":["II", "Ib", "Ic"], "category":"oxygen", "origin":"sn"},
    {"key":"O I 6300", "wavelength_vacuum":6302.05, "wavelength_air":6300.31, "sn_types":["II", "Ib", "Ic"], "category":"oxygen", "origin":"sn"},
    {"key":"O I 6364", "wavelength_vacuum":6365.54, "wavelength_air":6363.78, "sn_types":["II", "Ib", "Ic"], "category":"oxygen", "origin":"sn"},
    {"key":"O II 4119", "wavelength_vacuum":4119.00, "wavelength_air":4117.84, "sn_types":["SLSN-I"], "category":"oxygen", "origin":"sn"},
    {"key":"O II 4349", "wavelength_vacuum":4349.00, "wavelength_air":4347.78, "sn_types":["SLSN-I"], "category":"oxygen", "origin":"sn"},
    {"key":"O II 4416", "wavelength_vacuum":4416.00, "wavelength_air":4414.76, "sn_types":["SLSN-I"], "category":"oxygen", "origin":"sn"},
    {"key":"O II 4650", "wavelength_vacuum":4650.00, "wavelength_air":4648.70, "sn_types":["SLSN-I"], "category":"oxygen", "origin":"sn"},
    {"key":"Na I D2", "wavelength_vacuum":5891.58, "wavelength_air":5889.95, "sn_types":["Ia", "Ib", "Ic", "II"], "category":"sodium", "origin":"sn"},
    {"key":"Na I D1", "wavelength_vacuum":5897.56, "wavelength_air":5895.93, "sn_types":["Ia", "Ib", "Ic", "II"], "category":"sodium", "origin":"sn"},
    {"key":"Mg II 4481", "wavelength_vacuum":4481.20, "wavelength_air":4479.94, "sn_types":["Ia", "II"], "category":"magnesium", "origin":"sn"},
    {"key":"Mg I b", "wavelength_vacuum":5176.70, "wavelength_air":5175.26, "sn_types":["Ia", "II"], "category":"magnesium", "origin":"sn"},
    {"key":"Si II 6355", "wavelength_vacuum":6356.80, "wavelength_air":6355.04, "sn_types":["Ia"], "category":"silicon", "origin":"sn"},
    {"key":"Si II 5972", "wavelength_vacuum":5973.70, "wavelength_air":5972.05, "sn_types":["Ia"], "category":"silicon", "origin":"sn"},
    {"key":"Si II 4130", "wavelength_vacuum":4130.90, "wavelength_air":4129.74, "sn_types":["Ia"], "category":"silicon", "origin":"sn"},
    {"key":"Si III 4560", "wavelength_vacuum":4560.00, "wavelength_air":4558.72, "sn_types":["Ia"], "category":"silicon", "origin":"sn"},
    {"key":"Si III 5740", "wavelength_vacuum":5740.00, "wavelength_air":5738.41, "sn_types":["Ia"], "category":"silicon", "origin":"sn"},
    {"key":"S II 5455", "wavelength_vacuum":5455.30, "wavelength_air":5453.78, "sn_types":["Ia"], "category":"sulfur", "origin":"sn"},
    {"key":"S II 5641", "wavelength_vacuum":5641.50, "wavelength_air":5639.93, "sn_types":["Ia"], "category":"sulfur", "origin":"sn"},
    {"key":"[S II] 6717", "wavelength_vacuum":6718.29, "wavelength_air":6716.44, "sn_types":["II"], "category":"sulfur", "origin":"sn"},
    {"key":"[S II] 6731", "wavelength_vacuum":6732.67, "wavelength_air":6730.81, "sn_types":["II"], "category":"sulfur", "origin":"sn"},
    {"key":"[S III] 9069", "wavelength_vacuum":9071.10, "wavelength_air":9068.61, "sn_types":["II"], "category":"sulfur", "origin":"sn"},
    {"key":"[S III] 9532", "wavelength_vacuum":9533.20, "wavelength_air":9530.59, "sn_types":["II"], "category":"sulfur", "origin":"sn"},
    {"key":"Ca II K", "wavelength_vacuum":3934.78, "wavelength_air":3933.67, "sn_types":["Ia", "Ib", "Ic", "II"], "category":"calcium", "origin":"sn"},
    {"key":"Ca II H", "wavelength_vacuum":3969.59, "wavelength_air":3968.47, "sn_types":["Ia", "Ib", "Ic", "II"], "category":"calcium", "origin":"sn"},
    {"key":"Ca II 8498", "wavelength_vacuum":8500.36, "wavelength_air":8498.03, "sn_types":["Ia", "Ib", "Ic", "II"], "category":"calcium", "origin":"sn"},
    {"key":"Ca II 8542", "wavelength_vacuum":8544.44, "wavelength_air":8542.09, "sn_types":["Ia", "Ib", "Ic", "II"], "category":"calcium", "origin":"sn"},
    {"key":"Ca II 8662", "wavelength_vacuum":8664.52, "wavelength_air":8662.14, "sn_types":["Ia", "Ib", "Ic", "II"], "category":"calcium", "origin":"sn"},
    {"key":"[Ca II] 7291", "wavelength_vacuum":7293.50, "wavelength_air":7291.49, "sn_types":["II", "Ib", "Ic"], "category":"calcium", "origin":"sn"},
    {"key":"[Ca II] 7324", "wavelength_vacuum":7325.90, "wavelength_air":7323.88, "sn_types":["II", "Ib", "Ic"], "category":"calcium", "origin":"sn"},
    {"key":"Fe II 4924", "wavelength_vacuum":4925.30, "wavelength_air":4923.93, "sn_types":["Ia", "II"], "category":"iron", "origin":"sn"},
    {"key":"Fe II 5018", "wavelength_vacuum":5019.80, "wavelength_air":5018.40, "sn_types":["Ia", "II"], "category":"iron", "origin":"sn"},
    {"key":"Fe II 5169", "wavelength_vacuum":5170.50, "wavelength_air":5169.06, "sn_types":["Ia", "II"], "category":"iron", "origin":"sn"},
    {"key":"[Fe II] 7155", "wavelength_vacuum":7157.10, "wavelength_air":7155.13, "sn_types":["Ia"], "category":"iron", "origin":"sn"},
    {"key":"[Fe III] 4659", "wavelength_vacuum":4659.40, "wavelength_air":4658.10, "sn_types":["Ia"], "category":"iron", "origin":"sn"},
    {"key":"[Fe III] 5271", "wavelength_vacuum":5271.90, "wavelength_air":5270.43, "sn_types":["Ia"], "category":"iron", "origin":"sn"},
    {"key":"[Co III] 5890", "wavelength_vacuum":5893.00, "wavelength_air":5891.37, "sn_types":["Ia"], "category":"cobalt", "origin":"sn"},
    {"key":"[Co III] 6196", "wavelength_vacuum":6197.00, "wavelength_air":6195.29, "sn_types":["Ia"], "category":"cobalt", "origin":"sn"},
    {"key":"[Co II] 9342", "wavelength_vacuum":9344.00, "wavelength_air":9341.44, "sn_types":["Ia"], "category":"cobalt", "origin":"sn"},
    {"key":"[Ni II] 7378", "wavelength_vacuum":7379.80, "wavelength_air":7377.77, "sn_types":["Ia"], "category":"nickel", "origin":"sn"},
    {"key":"[Ni II] 7414", "wavelength_vacuum":7414.00, "wavelength_air":7411.96, "sn_types":["Ia"], "category":"nickel", "origin":"sn"},
    {"key":"[Ni III] 7890", "wavelength_vacuum":7891.00, "wavelength_air":7888.83, "sn_types":["Ia"], "category":"nickel", "origin":"sn"},
    {"key":"Ti II 4444", "wavelength_vacuum":4444.00, "wavelength_air":4442.75, "sn_types":["Ia-91bg"], "category":"titanium", "origin":"sn"},
    {"key":"Ti II 4553", "wavelength_vacuum":4553.00, "wavelength_air":4551.72, "sn_types":["Ia-91bg"], "category":"titanium", "origin":"sn"},
    {"key":"Cr II 4558", "wavelength_vacuum":4558.00, "wavelength_air":4556.72, "sn_types":["Ia"], "category":"chromium", "origin":"sn"},
    {"key":"Cr II 4824", "wavelength_vacuum":4824.00, "wavelength_air":4822.65, "sn_types":["Ia"], "category":"chromium", "origin":"sn"},
    {"key":"[Fe II] 8617", "wavelength_vacuum":8617.00, "wavelength_air":8615.00, "sn_types":["Ia", "II"], "category":"iron", "origin":"sn"},
    {"key":"[Fe II] 5535", "wavelength_vacuum":5535.00, "wavelength_air":5533.30, "sn_types":["Ia"], "category":"iron", "origin":"sn"},
    {"key":"[Ar III] 7136", "wavelength_vacuum":7137.76, "wavelength_air":7135.80, "sn_types":["II", "IIn"], "category":"argon", "origin":"sn"},
    {"key":"[Ar IV] 4740", "wavelength_vacuum":4740.10, "wavelength_air":4738.00, "sn_types":["II", "IIn"], "category":"argon", "origin":"sn"},
    {"key":"O VI 3811", "wavelength_vacuum":3811.35, "wavelength_air":3810.27, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"O VI 3834", "wavelength_vacuum":3834.16, "wavelength_air":3833.07, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"O IV 3410", "wavelength_vacuum":3409.80, "wavelength_air":3408.82, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"O V 5597", "wavelength_vacuum":5597.03, "wavelength_air":5595.48, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N V 4604", "wavelength_vacuum":4603.73, "wavelength_air":4602.44, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"C IV 5801", "wavelength_vacuum":5801.33, "wavelength_air":5799.72, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"C IV 5812", "wavelength_vacuum":5811.98, "wavelength_air":5810.37, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"C III 4647", "wavelength_vacuum":4647.42, "wavelength_air":4646.12, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"C III 4650", "wavelength_vacuum":4650.25, "wavelength_air":4648.95, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N II 4623", "wavelength_vacuum":4623.50, "wavelength_air":4622.21, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N II 4631", "wavelength_vacuum":4630.54, "wavelength_air":4629.24, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N III 4634", "wavelength_vacuum":4634.14, "wavelength_air":4632.65, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N III 4641", "wavelength_vacuum":4640.64, "wavelength_air":4639.14, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N V 4620", "wavelength_vacuum":4620.00, "wavelength_air":4618.60, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"O V 5114", "wavelength_vacuum":5114.06, "wavelength_air":5112.55, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"He II 4686", "wavelength_vacuum":4687.02, "wavelength_air":4685.39, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"He II 5412", "wavelength_vacuum":5413.00, "wavelength_air":5411.52, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N IV 7115", "wavelength_vacuum":7115.00, "wavelength_air":7113.40, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"Si IV 4089", "wavelength_vacuum":4088.86, "wavelength_air":4087.29, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"Si IV 4116", "wavelength_vacuum":4116.10, "wavelength_air":4114.53, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"N IV 3483", "wavelength_vacuum":3483.00, "wavelength_air":3481.70, "sn_types":["II", "IIb", "IIn"], "category":"flash_ion", "origin":"sn", "note":"flash-ionised"},
    {"key":"H-beta (gal)", "wavelength_vacuum":4862.72, "wavelength_air":4861.36, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"H-delta (gal)", "wavelength_vacuum":4102.90, "wavelength_air":4101.74, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He I 4471 (gal)", "wavelength_vacuum":4472.70, "wavelength_air":4471.45, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He I 5876 (gal)", "wavelength_vacuum":5877.30, "wavelength_air":5875.67, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He I 6678 (gal)", "wavelength_vacuum":6679.99, "wavelength_air":6678.15, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He I 7065 (gal)", "wavelength_vacuum":7067.10, "wavelength_air":7065.15, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He II 4686 (gal)", "wavelength_vacuum":4686.70, "wavelength_air":4685.39, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"Na I D2 (gal)", "wavelength_vacuum":5891.58, "wavelength_air":5889.95, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"Na I D1 (gal)", "wavelength_vacuum":5897.56, "wavelength_air":5895.93, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"Ca II K (gal)", "wavelength_vacuum":3934.78, "wavelength_air":3933.67, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"Ca II H (gal)", "wavelength_vacuum":3969.59, "wavelength_air":3968.47, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[Ca II] 7291 (gal)", "wavelength_vacuum":7293.50, "wavelength_air":7291.49, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[Ca II] 7324 (gal)", "wavelength_vacuum":7325.90, "wavelength_air":7323.88, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"Mg I 2852 (gal)", "wavelength_vacuum":2852.96, "wavelength_air":2852.12, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"Mg II 2796 (gal)", "wavelength_vacuum":2795.53, "wavelength_air":2794.71, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"Mg II 2803 (gal)", "wavelength_vacuum":2802.70, "wavelength_air":2801.87, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O II] 3727 (gal)", "wavelength_vacuum":3727.00, "wavelength_air":3725.94, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O II] 3726 (gal)", "wavelength_vacuum":3726.03, "wavelength_air":3724.97, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O II] 3728 (gal)", "wavelength_vacuum":3728.82, "wavelength_air":3727.76, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[Ne III] 3868 (gal)", "wavelength_vacuum":3868.00, "wavelength_air":3866.90, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O III] 4363 (gal)", "wavelength_vacuum":4363.21, "wavelength_air":4361.98, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He II 4541 (gal)", "wavelength_vacuum":4541.00, "wavelength_air":4539.73, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He I 4713 (gal)", "wavelength_vacuum":4713.14, "wavelength_air":4711.82, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He I 4922 (gal)", "wavelength_vacuum":4921.93, "wavelength_air":4920.56, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O III] 4959 (gal)", "wavelength_vacuum":4959.00, "wavelength_air":4957.62, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O III] 5007 (gal)", "wavelength_vacuum":5006.84, "wavelength_air":5005.44, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"He I 5015 (gal)", "wavelength_vacuum":5015.68, "wavelength_air":5014.28, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[N II] 6548 (gal)", "wavelength_vacuum":6548.04, "wavelength_air":6546.23, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[N II] 6583 (gal)", "wavelength_vacuum":6583.46, "wavelength_air":6581.64, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[S II] 6716 (gal)", "wavelength_vacuum":6716.44, "wavelength_air":6714.59, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[S II] 6731 (gal)", "wavelength_vacuum":6730.81, "wavelength_air":6728.95, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[Ne III] 3869 (gal)", "wavelength_vacuum":3869.86, "wavelength_air":3868.76, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"H-alpha (gal)", "wavelength_vacuum":6564.61, "wavelength_air":6562.80, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"H-gamma (gal)", "wavelength_vacuum":4341.69, "wavelength_air":4340.47, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O I] 6300 (gal)", "wavelength_vacuum":6302.05, "wavelength_air":6300.30, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[O I] 6364 (gal)", "wavelength_vacuum":6365.54, "wavelength_air":6363.78, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[Ne V] 3426 (gal)", "wavelength_vacuum":3426.85, "wavelength_air":3425.87, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"[Ar III] 7136 (gal)", "wavelength_vacuum":7137.76, "wavelength_air":7135.80, "sn_types":[], "category":"galaxy", "origin":"galaxy"},
    {"key":"H-beta (stellar)", "wavelength_vacuum":4862.72, "wavelength_air":4861.36, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"H-delta (stellar)", "wavelength_vacuum":4102.90, "wavelength_air":4101.74, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Na I D2 (stellar)", "wavelength_vacuum":5891.58, "wavelength_air":5889.95, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Na I D1 (stellar)", "wavelength_vacuum":5897.56, "wavelength_air":5895.93, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Mg I b (stellar)", "wavelength_vacuum":5176.70, "wavelength_air":5175.26, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Ca II K (stellar)", "wavelength_vacuum":3934.78, "wavelength_air":3933.67, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Ca II H (stellar)", "wavelength_vacuum":3969.59, "wavelength_air":3968.47, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Ca II 8498 (stellar)", "wavelength_vacuum":8500.36, "wavelength_air":8498.03, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Ca II 8542 (stellar)", "wavelength_vacuum":8544.44, "wavelength_air":8542.09, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Ca II 8662 (stellar)", "wavelength_vacuum":8664.52, "wavelength_air":8662.14, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"CH G-band (stellar)", "wavelength_vacuum":4305.60, "wavelength_air":4304.39, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"H-gamma (stellar)", "wavelength_vacuum":4341.69, "wavelength_air":4340.47, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"H-alpha (stellar)", "wavelength_vacuum":6564.61, "wavelength_air":6562.80, "sn_types":[], "category":"stellar_absorption", "origin":"stellar"},
    {"key":"Ba II 6142", "wavelength_vacuum":6141.71, "wavelength_air":6140.01, "sn_types":["II"], "category":"barium", "origin":"sn"},
    {"key":"Ba II 6497", "wavelength_vacuum":6498.72, "wavelength_air":6496.90, "sn_types":["II"], "category":"barium", "origin":"sn"},
    {"key":"Ba II 4554", "wavelength_vacuum":4554.03, "wavelength_air":4553.40, "sn_types":["II"], "category":"barium", "origin":"sn"},
    {"key":"Sc II 5527", "wavelength_vacuum":5526.79, "wavelength_air":5525.26, "sn_types":["II"], "category":"scandium", "origin":"sn"},
    {"key":"Sc II 5658", "wavelength_vacuum":5657.90, "wavelength_air":5656.33, "sn_types":["II"], "category":"scandium", "origin":"sn"},
    {"key":"Ti II 4172", "wavelength_vacuum":4171.93, "wavelength_air":4170.75, "sn_types":["Ia-91bg"], "category":"titanium", "origin":"sn"},
    {"key":"Sr II 4077", "wavelength_vacuum":4078.15, "wavelength_air":4077.00, "sn_types":["II"], "category":"strontium", "origin":"sn"},
    {"key":"Sr II 4215", "wavelength_vacuum":4216.00, "wavelength_air":4215.52, "sn_types":["II"], "category":"strontium", "origin":"sn"},
]

 # Legacy alias group definitions removed; aliases are defined in JSON

# Override with the packaged JSON line database to make this module a thin shim.
LINE_DB = list(_load_all_lines())

# ---------------------------------------------------------------------------
# Category descriptions
# ---------------------------------------------------------------------------
_CATS = _load_categories()
SN_LINE_CATEGORIES = {k: v.get("description", k) for k, v in _CATS.items()} if _CATS else {}

# ---------------------------------------------------------------------------
# Compatibility layer for existing GUI code
# ---------------------------------------------------------------------------
# Generate SUPERNOVA_EMISSION_LINES dictionary for existing emission line overlay dialog
SUPERNOVA_EMISSION_LINES = {}

# Define colors for each category (consistent with existing GUI expectations)
CATEGORY_COLORS = {k: v.get("color", "#888888") for k, v in _CATS.items()} if _CATS else {}

# Define helper functions for GUI compatibility
def _get_line_strength(line_data):
    """Determine line strength based on SN types and category"""
    line_name = line_data["key"]
    sn_types = line_data.get("sn_types", [])
    category = line_data["category"]
    note = line_data.get("note", "")
    
    # Very strong lines (key diagnostic features)
    if any(x in line_name for x in ["Si II 6355", "H-alpha", "He I 5876", "O I 7774"]):
        return "very_strong"
    
    # Flash-ionised lines are typically strong when present
    if "flash-ionised" in note or category == "flash_ion":
        return "strong"
    
    
    if any(x in line_name for x in ["H-beta", "H-gamma", "Si II 5972", "Ca II", "Fe II", "[O III] 5007"]):
        return "strong"
    
    # Medium strength (typical lines)
    if sn_types or category in ["hydrogen", "helium", "silicon", "calcium", "iron"]:
        return "medium"
    
    # Weak lines (less prominent)
    return "weak"

def _get_line_phase(line_data):
    """Determine typical observation phase for line"""
    line_name = line_data["key"]
    category = line_data["category"]
    note = line_data.get("note", "")
    
    # Flash-ionised lines appear in the first hours to days
    if "flash-ionised" in note or category == "flash_ion":
        return "very_early"
    
    # Early phase lines
    if category in ["helium", "carbon", "silicon"] and any(x in line_name for x in ["He I", "C II", "Si II", "Si III"]):
        return "early"
    
    # Maximum light lines  
    if category == "silicon" or "Si II" in line_name:
        return "maximum"
    
    # Late phase lines
    if category in ["iron", "calcium", "oxygen"] or any(x in line_name for x in ["Fe II", "Fe III", "Ca II 8", "O I"]):
        return "late"
    
    # Nebular phase lines
    if any(x in line_name for x in ["[Fe II]", "[Fe III]", "[Co III]", "[Ni II]", "[Ca II]"]):
        return "nebular"
    
    # Interaction signatures
    if category == "nitrogen" or "N II" in line_name:
        return "interaction"
    
    return "all"

def _get_line_type(line_data):
    """Determine if line is typically emission or absorption"""
    line_name = line_data["key"]
    category = line_data["category"]
    
    # Absorption lines
    if category in ["silicon", "interstellar", "stellar_absorption"]:
        return "absorption"
    
    # Forbidden lines are always emission
    if line_name.startswith("[") and "]" in line_name:
        return "emission"
    
    # Most SN lines are emission
    if line_data.get("sn_types"):
        return "emission"
    
    return "emission"

# Build SUPERNOVA_EMISSION_LINES dictionary from LINE_DB
for line_entry in LINE_DB:
    if line_entry["wavelength_air"] > 0 and line_entry["origin"] != "alias":
        line_name = line_entry["key"]
        
        SUPERNOVA_EMISSION_LINES[line_name] = {
            "wavelength": line_entry["wavelength_air"],  # Use air wavelength by default
            "wavelength_vacuum": line_entry["wavelength_vacuum"],
            "wavelength_air": line_entry["wavelength_air"],
            "type": _get_line_type(line_entry),
            "sn_types": line_entry.get("sn_types", []),
            "strength": _get_line_strength(line_entry),
            "color": CATEGORY_COLORS.get(line_entry["category"], "#888888"),
            "category": line_entry["category"],
            "phase": _get_line_phase(line_entry),
            "origin": line_entry["origin"],
            "description": f"{line_name} - {SN_LINE_CATEGORIES.get(line_entry['category'], 'Unknown category')}"
        }

# ---------------------------------------------------------------------------
# Other analysis parameters
# ---------------------------------------------------------------------------
REDSHIFT_TOLERANCE      = 0.001   # dimensionless
WAVELENGTH_TOLERANCE_Å  = 1.0     # Å
DEFAULT_VELOCITY_RANGE  = 30_000  # km s⁻¹

ANGSTROM_TO_NM          = 0.1
ANGSTROM_TO_MICRON      = 1e-4

OPTICAL_BLUE_MIN        = 3500
OPTICAL_BLUE_MAX        = 5000
OPTICAL_RED_MIN         = 5000
OPTICAL_RED_MAX         = 7000
NEAR_IR_MIN             = 7000
NEAR_IR_MAX             = 10000

MIN_CORRELATION_LENGTH  = 100     # Å
DEFAULT_TEMPLATE_RES    = 1.0     # Å px⁻¹
