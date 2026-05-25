"""
classifier.py
=============
ECG Accelerator Project — Week 2 Session 10
MAD-based AF classifier — Python reference model.

This is the GOLDEN REFERENCE. The SystemVerilog implementation
must produce identical results to this for every input.

Algorithm:
  1. Collect 8 RR intervals
  2. mean_RR = sum(RR) / 8
  3. MAD     = sum(|RR[i] - mean_RR|) / 8
  4. NV      = MAD / mean_RR
  5. NV > 0.08 → AF (output 2'b10), else Normal (output 2'b01)
"""

import numpy as np
import os

FS         = 360
WINDOW     = 8          # beats per classification window
THRESHOLD  = 0.08       # NV > 0.08 → AF
OUTPUT_DIR = r'D:\Project_3\python'

# Q1.15 constants — these are what the hardware uses
Q15_THRESHOLD = 2621    # round(0.08 × 32768)
Q15_DIV8      = 4096    # round(1/8  × 32768) = right shift 3
Q15_DIV30     = 1092    # round(1/30 × 32768)

# Output encoding
LABEL_NORMAL = 0b01     # 2'b01
LABEL_AF     = 0b10     # 2'b10
LABEL_INIT   = 0b00     # 2'b00 — not enough beats yet


# ─────────────────────────────────────────────────────────────────────────────
# FLOATING POINT CLASSIFIER (Python reference)
# ─────────────────────────────────────────────────────────────────────────────

def classify_window_float(rr_intervals):
    """
    Classify one 8-beat window using floating point arithmetic.
    This is the ground truth — hardware must match this.

    Parameters
    ----------
    rr_intervals : array of 8 RR intervals in samples (not ms)

    Returns
    -------
    label : int — LABEL_NORMAL or LABEL_AF
    nv    : float — normalised variability value
    """
    if len(rr_intervals) < WINDOW:
        return LABEL_INIT, 0.0

    rr       = np.array(rr_intervals[:WINDOW], dtype=np.float32)
    mean_rr  = np.mean(rr)
    mad      = np.mean(np.abs(rr - mean_rr))
    nv       = mad / mean_rr if mean_rr > 0 else 0.0

    label = LABEL_AF if nv > THRESHOLD else LABEL_NORMAL
    return label, nv


# ─────────────────────────────────────────────────────────────────────────────
# Q1.15 FIXED POINT CLASSIFIER (hardware reference model)
# ─────────────────────────────────────────────────────────────────────────────

def to_q15(x):
    """Convert float to Q1.15 integer."""
    return int(round(np.clip(x, -1.0, 0.99997) * 32768))


def q15_multiply(a, b):
    """
    Multiply two Q1.15 integers.
    16-bit × 16-bit → 32-bit product → shift right 15 → 16-bit result.
    This is exactly what the hardware does.
    """
    product = int(a) * int(b)        # 32-bit intermediate
    result  = product >> 15          # shift right 15
    return np.int16(np.clip(result, -32768, 32767))


def classify_window_q15(rr_intervals_samples):
    """
    Classify one 8-beat window using Q1.15 fixed point arithmetic.
    Mirrors the exact hardware computation.

    RR intervals arrive in samples (integer counts at 360 Hz).
    We normalise by dividing by max possible RR (65535) to fit Q1.15.

    Parameters
    ----------
    rr_intervals_samples : array of 8 RR intervals in samples

    Returns
    -------
    label    : int — LABEL_NORMAL or LABEL_AF
    nv_q15   : int — normalised variability in Q1.15
    """
    if len(rr_intervals_samples) < WINDOW:
        return LABEL_INIT, 0

    rr = np.array(rr_intervals_samples[:WINDOW], dtype=np.int32)

    # Step 1: sum RR intervals (accumulator)
    rr_sum = int(np.sum(rr))

    # Step 2: divide by 8 — right shift 3
    mean_rr = rr_sum >> 3

    # Step 3: compute absolute deviations and sum them
    deviations = np.abs(rr.astype(np.int32) - mean_rr)
    dev_sum    = int(np.sum(deviations))

    # Step 4: divide by 8 — right shift 3
    mad = dev_sum >> 3

    # Step 5: compute NV = MAD / mean_RR
    # In hardware: NV_q15 = (mad << 15) / mean_rr  (integer division)
    # This gives NV in Q1.15 format
    if mean_rr == 0:
        return LABEL_INIT, 0

    nv_q15 = (mad << 15) // mean_rr

    # Step 6: compare against threshold
    label = LABEL_AF if nv_q15 > Q15_THRESHOLD else LABEL_NORMAL

    return label, nv_q15


# ─────────────────────────────────────────────────────────────────────────────
# RUN CLASSIFIER OVER FULL RECORD
# ─────────────────────────────────────────────────────────────────────────────

def run_classifier(r_peaks, mode='float'):
    """
    Run classifier over all 8-beat windows in a record.
    Uses sliding window — advances one beat at a time.

    Returns arrays of:
      labels    : classification per window
      nv_values : NV value per window
      centres   : sample index of window centre beat
    """
    rr_samples = np.diff(r_peaks).astype(np.int32)
    n_windows  = len(rr_samples) - WINDOW + 1

    labels    = []
    nv_values = []
    centres   = []

    for i in range(n_windows):
        window = rr_samples[i : i + WINDOW]

        if mode == 'float':
            label, nv = classify_window_float(window)
        else:
            label, nv = classify_window_q15(window)

        labels.append(label)
        nv_values.append(nv)
        centres.append(r_peaks[i + WINDOW // 2])

    return (np.array(labels),
            np.array(nv_values),
            np.array(centres))


# ─────────────────────────────────────────────────────────────────────────────
# PRINT CLASSIFICATION SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(labels, nv_values, record_name, mode):
    n_normal = np.sum(labels == LABEL_NORMAL)
    n_af     = np.sum(labels == LABEL_AF)
    n_total  = len(labels)
    af_pct   = n_af / n_total * 100 if n_total > 0 else 0

    print(f"\n{'='*55}")
    print(f"  RECORD {record_name} — {mode.upper()} CLASSIFIER")
    print(f"{'='*55}")
    print(f"  Total windows    : {n_total}")
    print(f"  Normal windows   : {n_normal} ({100-af_pct:.1f}%)")
    print(f"  AF windows       : {n_af}     ({af_pct:.1f}%)")
    if np.mean(nv_values) > 2.0:  # Q1.15 raw integer — convert for display
        print(f"  Mean NV          : {np.mean(nv_values)/32768:.4f}  (raw Q1.15: {np.mean(nv_values):.0f})")
        print(f"  Max NV           : {np.max(nv_values)/32768:.4f}  (raw Q1.15: {np.max(nv_values):.0f})")
    else:
        print(f"  Mean NV          : {np.mean(nv_values):.4f}")
        print(f"  Max NV           : {np.max(nv_values):.4f}")
    print(f"  Threshold        : {THRESHOLD}")
    verdict = "AF DETECTED" if n_af > n_normal else "NORMAL"
    print(f"  Overall verdict  : {verdict}")
    print(f"{'='*55}")


# ─────────────────────────────────────────────────────────────────────────────
# COMPARE FLOAT VS Q1.15
# ─────────────────────────────────────────────────────────────────────────────

def compare_float_vs_q15(r_peaks, record_name):
    """
    Run both classifiers and compare results.
    Mismatches reveal quantisation errors that could affect hardware.
    """
    labels_f, nv_f, _ = run_classifier(r_peaks, mode='float')
    labels_q, nv_q, _ = run_classifier(r_peaks, mode='q15')

    mismatches = np.sum(labels_f != labels_q)
    total      = len(labels_f)

    print(f"\n  Record {record_name} — Float vs Q1.15 comparison:")
    print(f"  Total windows    : {total}")
    print(f"  Mismatches       : {mismatches}")
    print(f"  Agreement        : {(total-mismatches)/total*100:.2f}%")

    if mismatches > 0:
        idx = np.where(labels_f != labels_q)[0]
        print(f"  First mismatch at window {idx[0]}:")
        print(f"    Float  NV={nv_f[idx[0]]:.4f} → {'AF' if labels_f[idx[0]]==LABEL_AF else 'Normal'}")
        print(f"    Q1.15  NV={nv_q[idx[0]]/32768:.4f} → {'AF' if labels_q[idx[0]]==LABEL_AF else 'Normal'}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("="*55)
    print("  MAD AF CLASSIFIER — PYTHON REFERENCE MODEL")
    print("="*55)

    # Load detected R-peaks
    rp_n = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_detected_normal.npy'))
    rp_a = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_detected_af.npy'))

    # Run float classifier
    for rp, name in [(rp_n, '100 (Normal)'), (rp_a, '201 (AF)')]:
        labels, nv, _ = run_classifier(rp, mode='float')
        print_summary(labels, nv, name, 'float')

    # Run Q1.15 classifier
    for rp, name in [(rp_n, '100 (Normal)'), (rp_a, '201 (AF)')]:
        labels, nv, _ = run_classifier(rp, mode='q15')
        print_summary(labels, nv, name, 'q15')

    # Compare float vs Q1.15
    print("\n  --- Float vs Q1.15 Comparison ---")
    compare_float_vs_q15(rp_n, '100 (Normal)')
    compare_float_vs_q15(rp_a, '201 (AF)')

    # Save Q1.15 results for test vector generation
    labels_n, nv_n, centres_n = run_classifier(rp_n, mode='q15')
    labels_a, nv_a, centres_a = run_classifier(rp_a, mode='q15')

    np.save(os.path.join(OUTPUT_DIR, 'classifier_labels_normal.npy'), labels_n)
    np.save(os.path.join(OUTPUT_DIR, 'classifier_labels_af.npy'),     labels_a)
    np.save(os.path.join(OUTPUT_DIR, 'classifier_nv_normal.npy'),     nv_n)
    np.save(os.path.join(OUTPUT_DIR, 'classifier_nv_af.npy'),         nv_a)

    print("\n  ✓ Classifier results saved")
    print("\n" + "="*55)
    print("  CLASSIFIER COMPLETE")
    print("="*55)