"""
SNID-SAGE – SuperNova IDentification (Python port)
"""

from .io              import (read_spectrum, read_template,
                              load_templates, write_result,
                              write_detailed_result)
from .preprocessing    import (apodize, log_rebin,
                               apply_wavelength_mask,
                               fit_continuum_spline)                      # new thin wrapper
from .fft_tools        import (    # <<< was .correlation
    overlap, apply_filter as bandpass,
                                   # find_peaks became internal
)
from .snidtype         import (    # <<< was .utils
    compute_type_fractions, compute_subtype_fractions,
    SNIDResult
)
from .plotting         import (
    plot_comparison,
    plot_template_epochs,
)

__version__ = "1.0.0"

def get_version() -> str:          # small helper kept for outside code
    return __version__
