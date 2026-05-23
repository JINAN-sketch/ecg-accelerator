"""
apply_filter.py
===============
ECG Accelerator Project — Week 2
Applies the FIR filter to ECG signals and compares raw vs filtered.
"""

import numpy as np
from scipy.signal import lfilter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

FS         = 360
OUTPUT_DIR = r'D:\Project_3\python'


def apply_filter(signal, h):
    """
    Apply FIR filter to ECG signal using causal convolution.
    lfilter is causal — output at sample n depends only on
    current and past inputs. Essential for real-time hardware.
    """
    filtered = lfilter(h, [1.0], signal)
    return filtered.astype(np.float32)


def print_filter_stats(sig_raw, sig_filtered, r_peaks, record_name, fs=FS):
    """
    Compute peak-to-noise ratio before and after filtering.
    Baseline noise = std of signal in regions away from R-peaks.
    Excludes 100ms either side of each R-peak from noise calculation.
    """
    mask = np.ones(len(sig_filtered), dtype=bool)
    exclude = int(0.1 * fs)
    for rp in r_peaks:
        lo = max(0, rp - exclude)
        hi = min(len(sig_filtered), rp + exclude)
        mask[lo:hi] = False

    baseline_raw      = sig_raw[mask]
    baseline_filtered = sig_filtered[mask]

    noise_raw  = np.std(baseline_raw)
    noise_filt = np.std(baseline_filtered)
    peak_raw   = np.max(np.abs(sig_raw))
    peak_filt  = np.max(np.abs(sig_filtered))
    pnr_raw    = 20 * np.log10(peak_raw  / (noise_raw  + 1e-10))
    pnr_filt   = 20 * np.log10(peak_filt / (noise_filt + 1e-10))

    print(f"\n  Record {record_name}:")
    print(f"  Baseline noise raw      : {noise_raw:.4f} mV")
    print(f"  Baseline noise filtered : {noise_filt:.4f} mV")
    print(f"  Peak raw                : {peak_raw:.4f} mV")
    print(f"  Peak filtered           : {peak_filt:.4f} mV")
    print(f"  PNR raw                 : {pnr_raw:.1f} dB")
    print(f"  PNR filtered            : {pnr_filt:.1f} dB")
    print(f"  PNR improvement         : {pnr_filt - pnr_raw:+.1f} dB")


def plot_raw_vs_filtered(sig_raw, sig_filtered, record_name,
                          save_path=None, fs=FS):
    """
    Plot raw vs filtered ECG — 3 rows:
    Row 1: 10 second overlay
    Row 2: 3 second zoom
    Row 3: Difference signal (what the filter removed)
    """
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    fig.suptitle(f'Record {record_name} — Raw vs Filtered ECG',
                 fontsize=13, fontweight='bold')

    n_10s = min(10 * fs, len(sig_raw))
    n_3s  = min(3  * fs, len(sig_raw))
    t_10s = np.arange(n_10s) / fs
    t_3s  = np.arange(n_3s)  / fs

    # Row 1: 10 second overlay
    ax = axes[0]
    ax.plot(t_10s, sig_raw[:n_10s],
            '#BDBDBD', linewidth=0.6, label='Raw', alpha=0.8)
    ax.plot(t_10s, sig_filtered[:n_10s],
            '#2196F3', linewidth=1.0, label='Filtered')
    ax.set_title('10s Overlay — Raw (grey) vs Filtered (blue)')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (mV)')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)

    # Row 2: 3 second zoom
    ax = axes[1]
    ax.plot(t_3s, sig_raw[:n_3s],
            '#BDBDBD', linewidth=0.8, label='Raw', alpha=0.8)
    ax.plot(t_3s, sig_filtered[:n_3s],
            '#2196F3', linewidth=1.2, label='Filtered')
    ax.set_title('3s Zoom — noise removal visible')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (mV)')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)

    # Row 3: Difference signal
    ax = axes[2]
    diff = sig_raw[:n_10s] - sig_filtered[:n_10s]
    ax.plot(t_10s, diff, '#F44336', linewidth=0.6)
    ax.set_title('Difference (Raw - Filtered) — what the filter removed')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (mV)')
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color='black', linewidth=0.8, linestyle='--')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f'  ✓ Plot saved → {save_path}')
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("="*55)
    print("  APPLY FIR FILTER TO ECG SIGNALS")
    print("="*55)

    # Load signals, filter coefficients and ground truth R-peaks
    sig_n     = np.load(os.path.join(OUTPUT_DIR, 'ecg_normal.npy'))
    sig_a     = np.load(os.path.join(OUTPUT_DIR, 'ecg_af.npy'))
    h         = np.load(os.path.join(OUTPUT_DIR, 'fir_coefficients.npy'))
    r_peaks_n = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_normal.npy'))
    r_peaks_a = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_af.npy'))

    print(f"\n  Loaded normal signal : shape={sig_n.shape}")
    print(f"  Loaded AF signal     : shape={sig_a.shape}")
    print(f"  Loaded filter        : {len(h)} taps")

    # Apply filter
    print("\n  Filtering...")
    sig_n_filt = apply_filter(sig_n, h)
    sig_a_filt = apply_filter(sig_a, h)
    print("  ✓ Done")

    # Print statistics
    print("\n  --- Filter Statistics ---")
    print_filter_stats(sig_n, sig_n_filt, r_peaks_n, '100 (Normal)')
    print_filter_stats(sig_a, sig_a_filt, r_peaks_a, '201 (AF)')

    # Plot
    print("\n  Generating plots...")
    plot_raw_vs_filtered(
        sig_n, sig_n_filt, '100',
        save_path=os.path.join(OUTPUT_DIR, 'week2_filtered_normal.png'))
    plot_raw_vs_filtered(
        sig_a, sig_a_filt, '201',
        save_path=os.path.join(OUTPUT_DIR, 'week2_filtered_af.png'))

    # Save filtered signals for Pan-Tompkins
    np.save(os.path.join(OUTPUT_DIR, 'ecg_normal_filtered.npy'), sig_n_filt)
    np.save(os.path.join(OUTPUT_DIR, 'ecg_af_filtered.npy'),     sig_a_filt)
    print("\n  ✓ Filtered signals saved")

    print("\n" + "="*55)
    print("  SESSION 3 COMPLETE")
    print("="*55)