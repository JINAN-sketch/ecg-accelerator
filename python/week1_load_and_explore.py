"""
week1_load_and_explore.py
=========================
ECG Accelerator Project — Week 1
Goal: Load MIT-BIH records 100 (Normal Sinus Rhythm) and 201 (Atrial Fibrillation),
      compute RR statistics, generate analysis plots, save numpy arrays for Week 2.

CLINICAL BACKGROUND (essential for understanding what we are building):

  What is Atrial Fibrillation (AF)?
  ----------------------------------
  The heart's electrical system normally fires in a controlled sequence:
    SA node → AV node → Bundle of His → Purkinje fibres → ventricles contract.
  This produces the characteristic PQRST wave on an ECG:
    P  = atrial depolarisation (SA node fires, atria contract)
    QRS = ventricular depolarisation (large spike, ventricles contract — the R-peak)
    T  = ventricular repolarisation (heart resets)

  In AF, the atria fire chaotically (~350–600 times/second) instead of once per beat.
  The AV node acts as a gatekeeper — it randomly passes some of these impulses through.
  This causes two observable effects:
    1. The P-wave DISAPPEARS and is replaced by irregular low-amplitude "f-waves"
       (fibrillatory waves) — the atria are quivering, not contracting cleanly.
    2. The RR interval (time between consecutive R-peaks) becomes IRREGULAR.
       In normal rhythm, RR intervals are very consistent (± a few ms).
       In AF, the RR intervals are chaotic — the AV node fires whenever it
       randomly receives enough excitation from the fibrillating atria.

  Why do we use RR irregularity instead of P-wave shape for hardware detection?
  ------------------------------------------------------------------------------
  P-wave detection requires:
    - High SNR (P-wave is ~0.1–0.25 mV vs R-peak ~1–2 mV — 10x smaller)
    - Precise morphology analysis (shape matching)
    - Much more complex hardware: 2D correlator or neural network
  RR interval measurement requires:
    - Detecting R-peaks only (the largest feature in the signal — easy threshold)
    - Counting clock cycles between peaks (a simple counter)
    - Computing CoV of the last 8 intervals (accumulator + comparator)
  Hardware cost: R-peak only needs ~50 LUTs + 30-sample shift register.
  P-wave analysis would need 10x more resources. RR approach is the hardware choice.

  The clinical threshold:
  -----------------------
  Coefficient of Variation (CoV) = (std_dev / mean) × 100%
  CoV > 8% → classified as AF. This is the threshold we hardwire into the FSM.
  Normal sinus rhythm: CoV ≈ 1–4%
  Atrial fibrillation: CoV ≈ 15–40%
  The gap is large — a simple threshold is sufficient. No ML needed.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')          # Non-interactive backend — saves files without a display
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
FS = 360            # MIT-BIH sample rate (Hz) — fixed by the database standard
RECORD_NORMAL = '100'   # Normal sinus rhythm
RECORD_AF     = '201'   # Contains AF episodes (mixed — also has some normal beats)
OUTPUT_DIR    = r'D:\Project_3\python'
PLOT_PATH     = os.path.join(OUTPUT_DIR, 'week1_ecg_analysis.png')


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — DATA LOADING (real MIT-BIH or synthetic fallback)
# ─────────────────────────────────────────────────────────────────────────────

def load_mitbih_real(record_name):
    """
    Try to download and load a MIT-BIH record via wfdb from PhysioNet.
    Returns (signal_1d, r_peak_indices, beat_labels) or raises on failure.
    """
    import wfdb
    record = wfdb.rdrecord(record_name, pn_dir='mitdb')
    annotation = wfdb.rdann(record_name, 'atr', pn_dir='mitdb')
    signal = record.p_signal[:, 0].astype(np.float32)   # Lead I (channel 0)
    r_peaks = annotation.sample
    labels  = np.array(annotation.symbol)
    return signal, r_peaks, labels


def generate_pqrst_beat(fs, heart_rate_bpm, beat_type='N', noise_level=0.02):
    """
    Generate a single synthetic PQRST beat using Gaussian model.
    Based on the McSharry et al. (2003) synthetic ECG model (simplified).

    beat_type: 'N' = normal, 'A' = AF (no P-wave, irregular timing)

    Returns: (samples, r_peak_index_within_beat)
    """
    rr_samples = int(fs * 60.0 / heart_rate_bpm)
    t = np.linspace(0, rr_samples / fs, rr_samples)

    # PQRST Gaussian parameters: (amplitude, centre_fraction, width_seconds)
    # Centre fraction is position within the beat (0=start, 1=end)
    components = {
        'P': ( 0.15, 0.20, 0.025),   # P-wave: small, early
        'Q': (-0.10, 0.40, 0.010),   # Q-wave: small negative
        'R': ( 1.00, 0.45, 0.008),   # R-peak: tall narrow spike — the landmark
        'S': (-0.15, 0.50, 0.010),   # S-wave: small negative after R
        'T': ( 0.25, 0.70, 0.040),   # T-wave: broad positive
    }

    beat = np.zeros(rr_samples)
    r_idx = int(0.45 * rr_samples)  # R-peak centre index

    for name, (amp, centre_frac, width) in components.items():
        if name == 'P' and beat_type == 'A':
            # AF: P-wave is absent — replaced by low-amplitude fibrillatory noise
            # added separately below. Skip the clean P-wave Gaussian.
            continue
        centre = centre_frac * (rr_samples / fs)
        beat += amp * np.exp(-((t - centre) ** 2) / (2 * width ** 2))

    if beat_type == 'A':
        # f-waves (fibrillatory waves): irregular low-amplitude baseline oscillations
        # at ~350 Hz equivalent — but since we're at 360 Hz these alias to
        # visible low-frequency wobble. Model as sum of irregular sinusoids.
        f_wave = 0.05 * np.sin(2 * np.pi * 6.0 * t + np.random.uniform(0, 2*np.pi))
        f_wave += 0.03 * np.sin(2 * np.pi * 9.0 * t + np.random.uniform(0, 2*np.pi))
        beat += f_wave

    # Add realistic ECG noise: baseline wander + measurement noise
    beat += noise_level * np.random.randn(rr_samples)

    return beat, r_idx


def generate_synthetic_record(record_type='normal', duration_sec=30, fs=360):
    """
    Generate a synthetic MIT-BIH-faithful ECG signal.

    record_type = 'normal': steady heart rate ~75 bpm, small RR variation
    record_type = 'af':     irregular heart rate 50–130 bpm, AF beat type,
                            no P-waves, large RR variation

    Returns (signal, r_peak_indices, labels)
    """
    print(f"  Generating synthetic {record_type.upper()} ECG "
          f"({duration_sec}s at {fs} Hz)...")

    signal_parts = []
    r_peaks = []
    labels  = []
    current_sample = 0

    if record_type == 'normal':
        # Normal sinus rhythm: HR 70–80 bpm, slight HRV (~3% CoV)
        base_hr = 75.0
        target_samples = duration_sec * fs
        while current_sample < target_samples:
            # Small Gaussian variation in HR — realistic HRV
            hr = base_hr + np.random.normal(0, 2.0)
            hr = np.clip(hr, 55, 100)
            beat, r_local = generate_pqrst_beat(fs, hr, beat_type='N',
                                                 noise_level=0.015)
            r_peaks.append(current_sample + r_local)
            labels.append('N')
            signal_parts.append(beat)
            current_sample += len(beat)

    elif record_type == 'af':
        # AF: highly irregular RR intervals, no P-waves
        # Mean HR ~80 bpm but std is very high (~20 bpm)
        base_hr = 80.0
        target_samples = duration_sec * fs
        while current_sample < target_samples:
            # Large variation — this is what creates CoV > 8%
            hr = base_hr + np.random.normal(0, 20.0)
            hr = np.clip(hr, 45, 160)
            beat, r_local = generate_pqrst_beat(fs, hr, beat_type='A',
                                                 noise_level=0.02)
            r_peaks.append(current_sample + r_local)
            labels.append('A')
            signal_parts.append(beat)
            current_sample += len(beat)

    signal = np.concatenate(signal_parts).astype(np.float32)
    r_peaks = np.array(r_peaks, dtype=np.int32)
    labels  = np.array(labels)

    # Clip to exact requested length
    signal  = signal[:duration_sec * fs]
    mask    = r_peaks < len(signal)
    r_peaks = r_peaks[mask]
    labels  = labels[mask]

    return signal, r_peaks, labels


def load_record(record_name, record_type, duration_sec=30):
    """
    Try real MIT-BIH download; fall back to synthetic if it fails.
    record_type: 'normal' or 'af' — used only for fallback generation.
    """
    try:
        print(f"  Attempting to load real MIT-BIH record {record_name} from PhysioNet...")
        signal, r_peaks, labels = load_mitbih_real(record_name)
        print(f"  ✓ Using real MIT-BIH data (record {record_name})")
        return signal, r_peaks, labels, 'real'
    except Exception as e:
        print(f"  ✗ PhysioNet download failed: {e}")
        print(f"  → Falling back to synthetic MIT-BIH replica ({record_type})")
        signal, r_peaks, labels = generate_synthetic_record(
            record_type=record_type, duration_sec=duration_sec, fs=FS)
        print(f"  ✓ Using synthetic MIT-BIH replica")
        return signal, r_peaks, labels, 'synthetic'


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — RR INTERVAL COMPUTATION AND STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

def compute_rr_intervals(r_peaks, fs=360):
    """
    Compute RR intervals in milliseconds from R-peak sample indices.
    RR[i] = (r_peaks[i+1] - r_peaks[i]) / fs * 1000  (ms)
    """
    if len(r_peaks) < 2:
        return np.array([])
    rr_samples = np.diff(r_peaks)
    rr_ms = rr_samples / fs * 1000.0
    return rr_ms


def compute_statistics(signal, r_peaks, labels, rr_ms, record_name, data_mode):
    """
    Compute and print a full statistical summary.
    CoV (Coefficient of Variation) = std/mean × 100% is the key AF feature.
    """
    duration = len(signal) / FS

    # Label distribution
    unique_labels, counts = np.unique(labels, return_counts=True)
    label_dist = dict(zip(unique_labels, counts))

    print(f"\n{'='*55}")
    print(f"  RECORD {record_name}  [{data_mode.upper()}]")
    print(f"{'='*55}")
    print(f"  Sample count      : {len(signal):,}")
    print(f"  Duration          : {duration:.1f} s")
    print(f"  Beat count        : {len(r_peaks)}")
    print(f"  Label distribution: {label_dist}")
    print(f"  --- RR Interval Statistics ---")

    if len(rr_ms) == 0:
        print("  (insufficient beats)")
        return {}

    mean_rr = np.mean(rr_ms)
    std_rr  = np.std(rr_ms)
    cov_rr  = std_rr / mean_rr * 100.0    # KEY FEATURE: CoV > 8% → AF

    stats = {
        'mean_rr_ms':   mean_rr,
        'std_rr_ms':    std_rr,
        'min_rr_ms':    np.min(rr_ms),
        'max_rr_ms':    np.max(rr_ms),
        'cov_rr_pct':   cov_rr,
        'beat_count':   len(r_peaks),
        'duration_s':   duration,
    }

    print(f"  Mean RR           : {mean_rr:.1f} ms  ({60000/mean_rr:.1f} bpm)")
    print(f"  RR Std Dev        : {std_rr:.1f} ms")
    print(f"  Min RR            : {np.min(rr_ms):.1f} ms")
    print(f"  Max RR            : {np.max(rr_ms):.1f} ms")
    print(f"  CoV of RR         : {cov_rr:.2f}%")

    # Clinical interpretation
    # CoV > 8% is the threshold hardwired into the hardware classifier FSM
    if cov_rr > 8.0:
        print(f"  Clinical verdict  : ⚠ AF SUSPECTED (CoV {cov_rr:.1f}% > 8% threshold)")
    else:
        print(f"  Clinical verdict  : ✓ Normal sinus rhythm (CoV {cov_rr:.1f}% < 8%)")
    print(f"{'='*55}")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — PLOTTING
# ─────────────────────────────────────────────────────────────────────────────

def make_analysis_figure(sig_n, rp_n, sig_a, rp_a, rr_n, rr_a,
                          stats_n, stats_a, save_path):
    """
    Generate the 3-row × 2-column analysis figure.

    Row 1: 10-second raw ECG with R-peak markers
    Row 2: 3-beat zoom with PQRST labels on first beat (Normal only)
    Row 3: RR tachogram with mean ± 1σ shading
    """
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.suptitle('Week 1 — ECG Signal Analysis: Normal vs Atrial Fibrillation',
                 fontsize=14, fontweight='bold', y=0.98)

    # ── Colour scheme ──────────────────────────────────────────────────────
    C_NORMAL = '#2196F3'   # Blue — normal
    C_AF     = '#F44336'   # Red  — AF
    C_RPEAK  = '#FF9800'   # Orange — R-peak markers
    C_SHADE  = '#BDBDBD'   # Grey — ±1σ shading

    # ── ROW 1: 10-second raw ECG ───────────────────────────────────────────
    for col, (sig, rp, title, colour) in enumerate([
        (sig_n, rp_n, f'Normal (Record 100) — 10s ECG', C_NORMAL),
        (sig_a, rp_a, f'AF (Record 201) — 10s ECG',     C_AF),
    ]):
        ax = axes[0, col]
        n_plot = min(10 * FS, len(sig))
        t = np.arange(n_plot) / FS

        ax.plot(t, sig[:n_plot], colour, linewidth=0.8, label='ECG signal')

        # Mark R-peaks within the 10-second window
        rp_in_window = rp[rp < n_plot]
        ax.scatter(rp_in_window / FS, sig[rp_in_window],
                   color=C_RPEAK, s=40, zorder=5, label='R-peaks', marker='^')

        ax.set_title(title, fontsize=11)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (mV)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, n_plot / FS)

    # ── ROW 2: 3-beat zoom with PQRST labels ──────────────────────────────
    for col, (sig, rp, title, colour) in enumerate([
        (sig_n, rp_n, 'Normal — 3-beat zoom with PQRST labels', C_NORMAL),
        (sig_a, rp_a, 'AF — 3-beat zoom (no P-waves, irregular)', C_AF),
    ]):
        ax = axes[1, col]

        if len(rp) < 4:
            ax.text(0.5, 0.5, 'Insufficient beats', ha='center', va='center',
                    transform=ax.transAxes)
            continue

        # Show beats 1–3 (skip beat 0 to avoid edge effects)
        start_idx = max(0, rp[1] - int(0.1 * FS))
        end_idx   = min(len(sig), rp[4] + int(0.1 * FS)) if len(rp) > 4 else len(sig)
        t_zoom = (np.arange(end_idx - start_idx)) / FS
        sig_zoom = sig[start_idx:end_idx]

        ax.plot(t_zoom, sig_zoom, colour, linewidth=1.0)

        # Mark R-peaks in this window
        rp_zoom = rp[(rp >= start_idx) & (rp < end_idx)] - start_idx
        ax.scatter(rp_zoom / FS, sig_zoom[rp_zoom],
                   color=C_RPEAK, s=60, zorder=5, marker='^')

        # PQRST annotation on the FIRST visible beat (col==0 only for clarity)
        if col == 0 and len(rp_zoom) > 0:
            r_local = rp_zoom[0]
            rr_beat = (rp_zoom[1] - rp_zoom[0]) if len(rp_zoom) > 1 else int(0.8 * FS)

            # Estimated PQRST offsets relative to R-peak (in samples)
            labels_pqrst = {
                'P':  (-int(0.18 * FS), +0.15,  'P\n(atrial\ndepol.)'),
                'Q':  (-int(0.03 * FS), -0.12,  'Q'),
                'R':  (0,                +1.05,  'R\n(QRS\npeak)'),
                'S':  (+int(0.03 * FS), -0.17,  'S'),
                'T':  (+int(0.22 * FS), +0.25,  'T\n(ventricular\nrepol.)'),
            }
            for wave, (offset, y_frac, lbl) in labels_pqrst.items():
                x_idx = r_local + offset
                if 0 <= x_idx < len(sig_zoom):
                    ax.annotate(lbl,
                                xy=(x_idx / FS, sig_zoom[x_idx]),
                                xytext=(x_idx / FS, sig_zoom[x_idx] + y_frac * 0.3),
                                ha='center', fontsize=7,
                                arrowprops=dict(arrowstyle='->', color='black',
                                                lw=0.8),
                                color='black')

        ax.set_title(title, fontsize=11)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Amplitude (mV)')
        ax.grid(True, alpha=0.3)

    # ── ROW 3: RR tachogram ───────────────────────────────────────────────
    for col, (rr, stats, title, colour) in enumerate([
        (rr_n, stats_n, 'Normal — RR Tachogram (CoV = {:.1f}%)'.format(
            stats_n.get('cov_rr_pct', 0)), C_NORMAL),
        (rr_a, stats_a, 'AF — RR Tachogram (CoV = {:.1f}%)'.format(
            stats_a.get('cov_rr_pct', 0)), C_AF),
    ]):
        ax = axes[2, col]

        if len(rr) == 0:
            ax.text(0.5, 0.5, 'Insufficient RR intervals',
                    ha='center', va='center', transform=ax.transAxes)
            continue

        beat_numbers = np.arange(1, len(rr) + 1)
        mean_val = np.mean(rr)
        std_val  = np.std(rr)

        ax.plot(beat_numbers, rr, colour, linewidth=1.0, marker='o',
                markersize=3, label='RR interval')
        ax.axhline(mean_val, color='black', linewidth=1.2, linestyle='--',
                   label=f'Mean = {mean_val:.0f} ms')

        # ±1σ shading — visually shows spread
        ax.fill_between(beat_numbers,
                         mean_val - std_val, mean_val + std_val,
                         alpha=0.2, color=C_SHADE, label=f'±1σ ({std_val:.0f} ms)')

        # Clinical threshold line: mean ± 8% of mean
        thresh_line = mean_val * 0.08
        ax.axhline(mean_val + thresh_line, color='red', linewidth=0.8,
                   linestyle=':', alpha=0.7, label='±8% CoV boundary')
        ax.axhline(mean_val - thresh_line, color='red', linewidth=0.8,
                   linestyle=':', alpha=0.7)

        ax.set_title(title, fontsize=11)
        ax.set_xlabel('Beat number')
        ax.set_ylabel('RR interval (ms)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n  ✓ Figure saved → {save_path}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — SAVE NUMPY ARRAYS FOR WEEK 2
# ─────────────────────────────────────────────────────────────────────────────

def save_arrays(output_dir, sig_n, rp_n, lbl_n, sig_a, rp_a, lbl_a):
    """
    Save the six numpy arrays Week 2 will load directly.
    These are the 'interface contract' between Week 1 and Week 2.
    """
    os.makedirs(output_dir, exist_ok=True)
    files = {
        'ecg_normal.npy':    sig_n,
        'ecg_af.npy':        sig_a,
        'r_peaks_normal.npy': rp_n,
        'r_peaks_af.npy':    rp_a,
        'labels_normal.npy': lbl_n,
        'labels_af.npy':     lbl_a,
    }
    for fname, arr in files.items():
        path = os.path.join(output_dir, fname)
        np.save(path, arr)
        print(f"  Saved {fname:30s}  shape={arr.shape}  dtype={arr.dtype}")
    print(f"\n  ✓ All arrays saved to {output_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  ECG ACCELERATOR — WEEK 1: DATA LOADING & EXPLORATION")
    print("=" * 60)

    # ── Load records ──────────────────────────────────────────────────────
    print("\n[1/4] Loading ECG data...")
    sig_n, rp_n, lbl_n, mode_n = load_record(
        RECORD_NORMAL, record_type='normal', duration_sec=30)
    sig_a, rp_a, lbl_a, mode_a = load_record(
        RECORD_AF,     record_type='af',     duration_sec=30)

    # ── Compute RR intervals ──────────────────────────────────────────────
    print("\n[2/4] Computing RR intervals and statistics...")
    rr_n = compute_rr_intervals(rp_n, FS)
    rr_a = compute_rr_intervals(rp_a, FS)

    stats_n = compute_statistics(sig_n, rp_n, lbl_n, rr_n,
                                  RECORD_NORMAL, mode_n)
    stats_a = compute_statistics(sig_a, rp_a, lbl_a, rr_a,
                                  RECORD_AF,     mode_a)

    # Print the key hardware design insight
    print("\n  ─── HARDWARE DESIGN IMPLICATION ─────────────────────────")
    print(f"  Normal CoV: {stats_n.get('cov_rr_pct', 0):.1f}%  |  "
          f"AF CoV: {stats_a.get('cov_rr_pct', 0):.1f}%")
    print(f"  Decision threshold: CoV > 8%  →  MAD/mean_RR > 0.08")
    print(f"  In Q1.15 fixed-point: threshold = round(0.08 × 32768) = 2621")
    print(f"  This is the value hardwired into classifier_fsm.sv in Week 4.")
    print("  ──────────────────────────────────────────────────────────")

    # ── Generate and save the figure ──────────────────────────────────────
    print("\n[3/4] Generating analysis figure...")
    make_analysis_figure(sig_n, rp_n, sig_a, rp_a, rr_n, rr_a,
                          stats_n, stats_a, PLOT_PATH)

    # ── Save numpy arrays ─────────────────────────────────────────────────
    print("\n[4/4] Saving numpy arrays for Week 2...")
    save_arrays(OUTPUT_DIR, sig_n, rp_n, lbl_n, sig_a, rp_a, lbl_a)

    print("\n" + "=" * 60)
    print("  WEEK 1 COMPLETE.")
    print("  Files ready in D:\\Project_3\\python\\")
    print("=" * 60)


if __name__ == '__main__':
    main()
