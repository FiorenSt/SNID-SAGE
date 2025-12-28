"""
Spectrum plotting utilities for line detection
"""
import numpy as np
from scipy.signal import savgol_filter


# snid_sage.snid.preprocessing
# Import wrapper for backward compatibility
def apply_savgol_filter(wave, flux, window_length=11, polyorder=3):
    """
    Apply Savitzky-Golay filter to spectrum data.
    
    This wrapper is kept for backward compatibility.
    """
    from snid_sage.snid.preprocessing import savgol_filter_fixed
    return savgol_filter_fixed(flux, window_length, polyorder)


def plot_spectrum(ax, wavelength, flux, original_wave=None, original_flux=None, 
                  template_wave=None, template_flux=None, 
                  mode='flux', redshift=0.0, 
                  use_savgol=False, savgol_window=11, savgol_order=3,
                  mask_regions=None, theme_colors=None):
    """
    Plot a spectrum with optional template comparison
    
    Parameters:
    -----------
    ax : matplotlib.axes.Axes
        The axes to plot on
    wavelength : array-like
        Wavelength array for the spectrum
    flux : array-like
        Flux array for the spectrum
    original_wave : array-like, optional
        Original wavelength array for comparison
    original_flux : array-like, optional
        Original flux array for comparison
    template_wave : array-like, optional
        Template wavelength array for comparison
    template_flux : array-like, optional
        Template flux array for comparison
    mode : str, optional
        'flux' for regular flux, 'flat' for flattened spectrum
    redshift : float, optional
        Redshift value (z) for the template
    use_savgol : bool, optional
        Whether to apply Savitzky-Golay filter
    savgol_window : int, optional
        Window size for Savitzky-Golay filter
    savgol_order : int, optional
        Polynomial order for Savitzky-Golay filter
    mask_regions : list, optional
        List of (wavelength_min, wavelength_max) tuples to mask
    theme_colors : dict, optional
        Theme colors dictionary to apply to plot elements
    """
    # Clear the current axes
    ax.clear()
    
    # Set default colors from theme if provided
    if theme_colors is None:
        # Default to light theme colors
        theme_colors = {
            "plot_bg": "#ffffff",
            "plot_fg": "#000000",
            "plot_grid": "#cccccc",
            "plot_line": "#1f77b4"
        }
    
    # Apply theme colors to axes
    ax.set_facecolor(theme_colors["plot_bg"])
    ax.spines['bottom'].set_color(theme_colors["plot_fg"])
    ax.spines['top'].set_color(theme_colors["plot_fg"])
    ax.spines['right'].set_color(theme_colors["plot_fg"])
    ax.spines['left'].set_color(theme_colors["plot_fg"])
    ax.tick_params(axis='both', colors=theme_colors["plot_fg"])
    
    # Copy arrays to avoid modifying originals
    wavelength_plot = np.copy(wavelength)
    flux_plot = np.copy(flux)
    
    # Apply Savitzky-Golay filter if requested
    if use_savgol:
        flux_plot = apply_savgol_filter(wavelength_plot, flux_plot, 
                                       savgol_window, savgol_order)
    
    # Normalize if in flat mode
    if mode == 'flat':
        flux_plot = _normalize_spectrum(wavelength_plot, flux_plot)
        
        if original_flux is not None and original_wave is not None:
            original_flux = _normalize_spectrum(original_wave, original_flux)
            
        if template_flux is not None and template_wave is not None:
            template_flux = _normalize_spectrum(template_wave, template_flux)
    
    # Plot main spectrum
    main_color = theme_colors.get("plot_line", "#1f77b4")  # Default to matplotlib blue
    ax.plot(wavelength_plot, flux_plot, color=main_color, linewidth=1.2, label='Current')
    
    # Plot original spectrum for comparison if provided
    if original_flux is not None and original_wave is not None:
        ax.plot(original_wave, original_flux, color='gray', linewidth=1.0, 
               alpha=0.7, label='Original')
    
    # Plot template if provided, adjusting for redshift
    if template_flux is not None and template_wave is not None:
        # Adjust wavelength for redshift: λ_obs = λ_emit * (1 + z)
        template_wave_adjusted = template_wave * (1 + redshift)
        
        # Plot with different style
        ax.plot(template_wave_adjusted, template_flux, 
               color='red', linewidth=1.0, alpha=0.8, linestyle='--',
               label=f'Template (z={redshift:.6f})')
    
    # Add legend
    ax.legend(loc='upper right')
    
    # Highlight masked regions if provided
    if mask_regions:
        for wmin, wmax in mask_regions:
            ax.axvspan(wmin, wmax, color='gray', alpha=0.2)
    
    # Set labels with theme colors
    ax.set_xlabel('Wavelength (Å)', color=theme_colors["plot_fg"])
    ax.set_ylabel('Flux' if mode == 'flux' else 'Flattened Flux', color=theme_colors["plot_fg"])
    ax.grid(True, linestyle='--', alpha=0.5, color=theme_colors["plot_grid"])
    
    # Update title to include information about smoothing if used
    title = "Spectrum Analysis"
    if use_savgol:
        title += f" (Savitzky-Golay: window={savgol_window}, order={savgol_order})"
    
    ax.set_title(title, color=theme_colors["plot_fg"])
    
    # Update legend text color
    leg = ax.legend(loc='upper right')
    for text in leg.get_texts():
        text.set_color(theme_colors["plot_fg"])
        
    # Update x and y tick labels color
    for label in ax.get_xticklabels():
        label.set_color(theme_colors["plot_fg"])
    for label in ax.get_yticklabels():
        label.set_color(theme_colors["plot_fg"])
    
    return ax


def _normalize_spectrum(wavelength, flux):
    """Normalize spectrum flux to unit median"""
    try:
        median_flux = np.median(flux)
        if median_flux != 0:
            return flux / median_flux
        else:
            return flux
    except Exception:
        return flux


def wavelength_to_velocity(w1, w2):
    """Convert wavelength difference to velocity in km/s"""
    # Avoid division by zero or very small values
    if abs(w1) < 1e-10:
        return 0.0
    
    # Relativistic velocity formula: v = c * (λ_obs - λ_rest) / λ_rest
    c = 299792.458  # Speed of light in km/s
    return c * (w2 - w1) / w1


def compute_effective_sn_redshift(host_redshift: float, velocity_kms: float, use_relativistic: bool = True) -> float:
    """Compute effective SN redshift given host redshift and ejecta velocity.

    Positive velocity means approaching observer (blueshift), which reduces the
    effective redshift of SN features relative to the host.

    If use_relativistic is True, apply the multiplicative composition of
    cosmological and peculiar (Doppler) shifts:

        (1 + z_eff) = (1 + z_host) * sqrt((1 - beta) / (1 + beta))

    where beta = v/c with v>0 for approaching. For small |beta|, this reduces to
    z_eff ≈ z_host - v/c.
    """
    c = 299792.458
    try:
        beta = float(velocity_kms) / c
        if use_relativistic and abs(beta) > 1e-2:
            # Relativistic Doppler factor for approaching source (blueshift)
            doppler_factor = ((1.0 - beta) / (1.0 + beta)) ** 0.5
            return (1.0 + float(host_redshift)) * doppler_factor - 1.0
        else:
            return float(host_redshift) - beta
    except Exception:
        return float(host_redshift)


def apply_moving_average(data, window_size=5):
    """Apply simple moving average smoothing"""
    if window_size <= 1:
        return data
    
    # Ensure window size is not larger than data
    window_size = min(window_size, len(data))
    
    # Simple moving average
    smoothed = np.convolve(data, np.ones(window_size)/window_size, mode='same')
    return smoothed 