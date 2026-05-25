"""
pan_tompkins.py
===============
ECG Accelerator Project — Week 2
Pan-Tompkins R-peak detection algorithm.

Pipeline:
  Filtered ECG → Differentiate → Square → Moving Window Integrate
               → Adaptive Threshold → Refractory Period → Refine → R-peaks
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

FS         = 360
OUTPUT_DIR = r'D:\Project_3\python'

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — DIFFERENTIATION
# ─────────────────────────────────────────────────────────────────────────────

def differentiate(signal):
    """
    Pan-Tompkins derivative filter.
    y[n] = (1/8)(2x[n] + x[n-1] - x[n-3] - 2x[n-4])

    Highlights steep slopes — R-peak has steepest slope in ECG.
    5-point weighted derivative, robust against single-sample noise.
    """
    n = len(signal)
    diff = np.zeros(n)
    for i in range(4, n):
        diff[i] = (1/8) * (2*signal[i] + signal[i-1]
                           - signal[i-3] - 2*signal[i-4])
    return diff.astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — SQUARING
# ─────────────────────────────────────────────────────────────────────────────

def square(signal):
    """
    Element-wise squaring.
    Makes all values positive, amplifies large slopes non-linearly.
    A slope of 2 → 4, a slope of 0.1 → 0.01
    Noise suppressed, R-peak emphasised.
    """
    return (signal ** 2).astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — MOVING WINDOW INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

def moving_window_integrate(signal, window_size=30):
    """
    Moving window integrator.
    y[n] = (1/30)(x[n] + x[n-1] + ... + x[n-29])

    Window size = 30 samples = 83ms at 360 Hz.
    Slightly wider than widest QRS (~70ms) — captures full QRS energy.
    Converts sharp energy spike into broad smooth bump.

    Hardware note: divide by 30 = multiply by 1/30 = 1092 in Q1.15
    """
    n = len(signal)
    integrated = np.zeros(n)
    for i in range(window_size - 1, n):
        integrated[i] = np.sum(signal[i - window_size + 1 : i + 1]) / window_size
    return integrated.astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — ADAPTIVE THRESHOLD + STEP 5 — REFRACTORY PERIOD
# ─────────────────────────────────────────────────────────────────────────────

def detect_peaks(integrated, fs=FS):
    """
    Adaptive threshold peak detection with refractory period.

    Threshold tracks signal level:
      - Updates upward when a peak is detected
      - Decays slowly between peaks (handles baseline wander)

    Refractory period = 200ms = 72 samples
      - After each detection, ignore signal for 72 samples
      - Physiologically impossible to have two beats within 200ms

    Returns array of detected peak indices (in integrated signal space).
    These are later refined to true R-peak locations by refine_to_rpeak().
    """
    refractory   = int(0.2 * fs)    # 200ms = 72 samples
    n            = len(integrated)
    r_peaks      = []

    # Initialise thresholds from first 2 seconds of signal
    init_window  = integrated[:2 * fs]
    signal_level = np.max(init_window)
    noise_level  = np.mean(init_window)
    threshold    = noise_level + 0.25 * (signal_level - noise_level)

    i = 0
    while i < n:
        if integrated[i] > threshold:
            # Find the peak of this bump
            while i < n - 1 and integrated[i] <= integrated[i + 1]:
                i += 1
            peak_idx   = i
            peak_value = integrated[peak_idx]

            # Update signal level and threshold
            signal_level = 0.125 * peak_value + 0.875 * signal_level
            threshold    = noise_level + 0.25 * (signal_level - noise_level)

            r_peaks.append(peak_idx)

            # Apply refractory period
            i = peak_idx + refractory

        else:
            # Update noise level
            noise_level = 0.125 * integrated[i] + 0.875 * noise_level
            threshold   = noise_level + 0.25 * (signal_level - noise_level)
            i += 1

    return np.array(r_peaks, dtype=np.int64)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — REFINE TO TRUE R-PEAK
# ─────────────────────────────────────────────────────────────────────────────

def refine_to_rpeak(filtered_signal, peak_indices, fs=FS):
    """
    Snap each detected index to the true R-peak in the filtered signal.

    WHY THIS IS NEEDED:
    The moving window integrator introduces a delay of ~15 samples.
    The adaptive threshold fires on the integrated bump peak, which is
    shifted forward in time relative to the actual R-peak tip.
    Without refinement, detected indices are ~15-30 samples late —
    outside the ±18 sample AHA tolerance window.

    FIX:
    For each detected index, search ±150ms (±54 samples) in the
    filtered signal and snap to the maximum absolute amplitude.
    The R-peak is always the largest feature — this reliably finds it.
    """
    search  = int(0.15 * fs)
    refined = []
    for idx in peak_indices:
        lo        = max(0, idx - search)
        hi        = min(len(filtered_signal), idx + search)
        local_max = lo + np.argmax(filtered_signal[lo:hi])  # remove np.abs
        refined.append(local_max)
    return np.array(refined, dtype=np.int64)


# ─────────────────────────────────────────────────────────────────────────────
# FULL PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def pan_tompkins(filtered_signal, fs=FS):
    """
    Full Pan-Tompkins pipeline.
    Input : filtered ECG signal (output of apply_filter.py)
    Output: array of detected R-peak sample indices (refined to filtered signal)
    """
    diff       = differentiate(filtered_signal)
    squared    = square(diff)
    integrated = moving_window_integrate(squared)
    r_peaks    = detect_peaks(integrated, fs)
    r_peaks    = refine_to_rpeak(filtered_signal, r_peaks, fs)  # snap to true R-peak
    return r_peaks, diff, squared, integrated


# ─────────────────────────────────────────────────────────────────────────────
# PLOTTING
# ─────────────────────────────────────────────────────────────────────────────

def plot_pipeline(filtered, diff, squared, integrated, r_peaks,
                  record_name, save_path=None, fs=FS):
    """
    Plot all 4 stages of the Pan-Tompkins pipeline for 5 seconds.
    """
    n    = min(5 * fs, len(filtered))
    t    = np.arange(n) / fs
    rp   = r_peaks[r_peaks < n]

    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    fig.suptitle(f'Record {record_name} — Pan-Tompkins Pipeline',
                 fontsize=13, fontweight='bold')

    data = [
        (filtered,   '#2196F3', 'Stage 1: Filtered ECG'),
        (diff,       '#9C27B0', 'Stage 2: Differentiated'),
        (squared,    '#FF9800', 'Stage 3: Squared'),
        (integrated, '#4CAF50', 'Stage 4: Integrated + R-peaks'),
    ]

    for idx, (sig, colour, title) in enumerate(data):
        ax = axes[idx]
        ax.plot(t, sig[:n], colour, linewidth=0.8)
        if idx == 3:
            # Find integrated bump peak nearest each refined R-peak
            search = int(0.15 * fs)
            bump_peaks = []
            for r in rp:
                lo = max(0, r - search)
                hi = min(n, r + search)
                bump_peaks.append(lo + np.argmax(integrated[lo:hi]))
            bump_peaks = np.array(bump_peaks)
            ax.scatter(bump_peaks / fs, integrated[bump_peaks],
                       color='red', s=50, zorder=5,
                       marker='v', label='Detected peaks')
            ax.legend(loc='upper right', fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel('Time (s)')
        ax.grid(True, alpha=0.3)

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
    print("  PAN-TOMPKINS R-PEAK DETECTION")
    print("="*55)

    # Load filtered signals
    sig_n = np.load(os.path.join(OUTPUT_DIR, 'ecg_normal_filtered.npy'))
    sig_a = np.load(os.path.join(OUTPUT_DIR, 'ecg_af_filtered.npy'))

    print(f"\n  Loaded normal filtered : shape={sig_n.shape}")
    print(f"  Loaded AF filtered     : shape={sig_a.shape}")

    # Run Pan-Tompkins
    print("\n  Running Pan-Tompkins detector...")
    rp_n, diff_n, sq_n, int_n = pan_tompkins(sig_n)
    rp_a, diff_a, sq_a, int_a = pan_tompkins(sig_a)

    print(f"\n  Record 100 — detected {len(rp_n)} R-peaks")
    print(f"  Record 201 — detected {len(rp_a)} R-peaks")

    # Plot pipelines
    print("\n  Generating pipeline plots...")
    plot_pipeline(sig_n, diff_n, sq_n, int_n, rp_n, '100',
                  save_path=os.path.join(OUTPUT_DIR,
                  'week2_pantompkins_normal.png'))
    plot_pipeline(sig_a, diff_a, sq_a, int_a, rp_a, '201',
                  save_path=os.path.join(OUTPUT_DIR,
                  'week2_pantompkins_af.png'))

    # Save detected R-peaks
    np.save(os.path.join(OUTPUT_DIR, 'r_peaks_detected_normal.npy'), rp_n)
    np.save(os.path.join(OUTPUT_DIR, 'r_peaks_detected_af.npy'),     rp_a)
    print("\n  ✓ Detected R-peaks saved")

    print("\n" + "="*55)
    print("  SESSION 4 COMPLETE")
    print("="*55)