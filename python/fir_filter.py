"""
fir_filter.py
=============
ECG Accelerator Project — Week 2
Designs a 33-tap linear-phase FIR bandpass filter.
Passband: 0.5–40 Hz at 360 Hz sample rate.
"""

import numpy as np
from scipy.signal import firwin, freqz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
FS = 360 # sample rate
NUMTAPS = 33 # number of taps/ filter length
F_LOW = 0.5 #lower freq cutoff
F_HIGH = 40.0 #upper freq cutoff
OUTPUT_DIR = r'D:\Project_3\python'

# ─────────────────────────────────────────────────────────────────────────────
# FILTER DESIGN
# ─────────────────────────────────────────────────────────────────────────────

def design_fir_filter(numtaps = NUMTAPS,f_low = F_LOW,f_high = F_HIGH, fs = FS):
    """
    Design a linear-phase FIR bandpass filter using firwin.

    firwin uses the window method:
      1. Compute ideal sinc impulse response for the cutoff frequencies
      2. Multiply by a Hamming window to suppress stopband ripple
      3. Result: numtaps coefficients (the filter's impulse response)

    Parameters
    ----------
    numtaps : int   — number of filter taps (must be odd)
    f_low   : float — lower cutoff frequency (Hz)
    f_high  : float — upper cutoff frequency (Hz)
    fs      : int   — sample rate (Hz)

    Returns
    -------
    h : numpy array, shape (numtaps,) — filter coefficients
    """
    # Normalise cutoffs to Nyquist (firwin expects values 0–1 where 1 = Nyquist)
    nyquist = fs/ 2.0
    low = f_low / nyquist
    high = f_high / nyquist

    # Design the filter
    # pass_zero=False tells firwin this is a bandpass (not lowpass)

    h = firwin(numtaps, [low,high],pass_zero=False,window='hamming')
    return h

# ─────────────────────────────────────────────────────────────────────────────
# FREQUENCY RESPONSE
# ─────────────────────────────────────────────────────────────────────────────

def plot_frequency_response(h, fs = FS, save_path = None):
    """
    Plot the frequency response of the FIR filter.
    Shows magnitude (dB) vs frequency (Hz).
    """
    # freqz computes H(e^jw) — the filter's frequency response
    # worN=8192 gives 8192 frequency points for smooth plot
    w, H = freqz(h, worN=8192,fs=fs)

    magnitude_db = 20 * np.log10(np.abs(H)  + 1e-10)

    fig, axes = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle('FIR Bandpass Filter — Frequency Response', fontsize=13)
#_______Magnitude reponse(db)_______________________________
    ax = axes[0]
    ax.plot(w, magnitude_db, '#2196F3', linewidth=1.5)
    ax.axvline(F_LOW,  color='red',   linestyle='--', linewidth=1,
               label=f'Lower cutoff ({F_LOW} Hz)')
    ax.axvline(F_HIGH, color='green', linestyle='--', linewidth=1,
               label=f'Upper cutoff ({F_HIGH} Hz)')
    ax.axhline(-3, color='orange', linestyle=':', linewidth=1,
               label='-3 dB point')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Magnitude (dB)')
    ax.set_title('Magnitude Response')
    ax.set_xlim(0, fs / 2)
    ax.set_ylim(-80, 5)
    ax.legend()
    ax.grid(True, alpha=0.3)

# ── Passband zoom ─────────────────────────────────────────────────────
    ax = axes[1]
    ax.plot(w, magnitude_db, '#2196F3', linewidth=1.5)
    ax.axvline(F_LOW,  color='red',   linestyle='--', linewidth=1,
               label=f'Lower cutoff ({F_LOW} Hz)')
    ax.axvline(F_HIGH, color='green', linestyle='--', linewidth=1,
               label=f'Upper cutoff ({F_HIGH} Hz)')
    ax.axhline(-3, color='orange', linestyle=':', linewidth=1,
               label='-3 dB point')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Magnitude (dB)')
    ax.set_title('Passband Zoom (0–60 Hz)')
    ax.set_xlim(0, 60)
    ax.set_ylim(-80, 5)
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f'  ✓ Filter response saved → {save_path}')
    plt.close()

# ─────────────────────────────────────────────────────────────────────────────
# PRINT FILTER SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_filter_summary(h, fs=FS):
    """
    Print key filter properties.
    """
    delay_samples = (len(h) - 1) // 2
    delay_ms      = delay_samples / fs * 1000

    print(f"\n{'='*50}")
    print(f"  FIR FILTER SUMMARY")
    print(f"{'='*50}")
    print(f"  Taps          : {len(h)}")
    print(f"  Passband      : {F_LOW} – {F_HIGH} Hz")
    print(f"  Sample rate   : {fs} Hz")
    print(f"  Window        : Hamming")
    print(f"  Group delay   : {delay_samples} samples = {delay_ms:.1f} ms")
    print(f"  Coefficients  :")
    for i, coef in enumerate(h):
        print(f"    h[{i:02d}] = {coef:+.6f}")
    print(f"{'='*50}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Designing FIR bandpass filter...")

    h = design_fir_filter()

    print_filter_summary(h)

    plot_frequency_response(
        h,
        save_path=os.path.join(OUTPUT_DIR, 'week2_filter_response.png')
    )

    # Save coefficients for use in other modules
    np.save(os.path.join(OUTPUT_DIR, 'fir_coefficients.npy'), h)
    print(f"\n  ✓ Coefficients saved → fir_coefficients.npy")
    print("\nDone.")
