"""
validate_detector.py
====================
ECG Accelerator Project — Week 1 Session 9
Validates Pan-Tompkins detector against MIT-BIH ground truth annotations.

Metrics:
  Sensitivity (Se)          = TP / (TP + FN)
  Positive Predictivity (PP) = TP / (TP + FP)

AHA standard: both Se and PP must exceed 95% for a clinical detector.
Tolerance window: ±18 samples = ±50ms at 360 Hz (AHA standard).
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

FS            = 360
TOLERANCE     = 18    # ±18 samples = ±50ms AHA standard
OUTPUT_DIR    = r'D:\Project_3\python'

# Beat labels to include in validation
# We only validate against normal-ish beats — exclude rhythm annotations
# and non-beat markers
VALID_LABELS  = {'N', 'L', 'R', 'A', 'a', 'J', 'j', 'V', 'F', 'e', 'E'}


def filter_ground_truth(r_peaks_gt, labels):
    """
    Filter ground truth to only include real beats.
    Excludes rhythm annotations (+), noise (~), and non-conducted P-waves (x).
    """
    mask = np.array([l in VALID_LABELS for l in labels])
    return r_peaks_gt[mask]


def match_peaks(detected, ground_truth, tolerance=TOLERANCE):
    """
    Match detected peaks to ground truth peaks within ±tolerance samples.

    Algorithm:
      For each ground truth peak, find the closest detected peak.
      If within tolerance → True Positive (TP)
      Each detected peak can only match one ground truth peak.

    Returns:
      tp : number of true positives
      fp : number of false positives (detected but no matching GT)
      fn : number of false negatives (GT beat not detected)
      matched_pairs : list of (gt_idx, det_idx) matched pairs
    """
    detected   = np.sort(detected)
    ground_truth = np.sort(ground_truth)

    matched_gt  = set()
    matched_det = set()
    matched_pairs = []

    for i, gt in enumerate(ground_truth):
        # Find detected peaks within tolerance
        diffs = np.abs(detected - gt)
        candidates = np.where(diffs <= tolerance)[0]

        if len(candidates) == 0:
            continue

        # Pick closest unmatched detected peak
        candidates = [c for c in candidates if c not in matched_det]
        if len(candidates) == 0:
            continue

        best = candidates[np.argmin(diffs[candidates])]
        matched_gt.add(i)
        matched_det.add(best)
        matched_pairs.append((gt, detected[best]))

    tp = len(matched_pairs)
    fn = len(ground_truth) - tp
    fp = len(detected) - tp

    return tp, fp, fn, matched_pairs


def compute_metrics(tp, fp, fn):
    """
    Compute sensitivity and positive predictivity.
    """
    se = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    pp = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    return se, pp


def print_validation_report(record_name, tp, fp, fn, se, pp):
    """
    Print a formatted validation report.
    """
    print(f"\n{'='*55}")
    print(f"  RECORD {record_name} — VALIDATION REPORT")
    print(f"{'='*55}")
    print(f"  True Positives  (TP) : {tp:5d}  (correctly detected)")
    print(f"  False Positives (FP) : {fp:5d}  (detected, not a real beat)")
    print(f"  False Negatives (FN) : {fn:5d}  (missed real beat)")
    print(f"  {'─'*45}")
    print(f"  Sensitivity     (Se) : {se:.2f}%")
    print(f"  Positive Pred.  (PP) : {pp:.2f}%")
    print(f"  AHA threshold        : 95.00%")

    se_pass = "✓ PASS" if se >= 95 else "✗ FAIL"
    pp_pass = "✓ PASS" if pp >= 95 else "✗ FAIL"
    print(f"  Se status            : {se_pass}")
    print(f"  PP status            : {pp_pass}")
    print(f"{'='*55}")


def plot_validation(sig_filtered, detected, ground_truth,
                    matched_pairs, record_name, save_path=None, fs=FS):
    """
    Plot 5 seconds of signal with:
    - Detected peaks (blue triangles)
    - Ground truth peaks (green circles)
    - False positives (red X)
    - False negatives (orange diamonds)
    """
    n    = min(5 * fs, len(sig_filtered))
    t    = np.arange(n) / fs

    det_in  = detected[detected < n]
    gt_in   = ground_truth[ground_truth < n]

    matched_det = set(d for _, d in matched_pairs if d < n)
    matched_gt  = set(g for g, _ in matched_pairs if g < n)

    fp_peaks = [d for d in det_in if d not in matched_det]
    fn_peaks = [g for g in gt_in  if g not in matched_gt]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(t, sig_filtered[:n], '#90CAF9', linewidth=0.8, label='Filtered ECG')

    # Ground truth — green circles
    if len(gt_in) > 0:
        ax.scatter(np.array(list(matched_gt)) / fs,
                   sig_filtered[list(matched_gt)],
                   color='#4CAF50', s=60, zorder=5,
                   marker='o', label='Ground truth (matched)')

    # Detected — blue triangles
    if len(matched_det) > 0:
        ax.scatter(np.array(list(matched_det)) / fs,
                   sig_filtered[list(matched_det)],
                   color='#2196F3', s=40, zorder=6,
                   marker='^', label='Detected (TP)')

    # False positives — red X
    if len(fp_peaks) > 0:
        ax.scatter(np.array(fp_peaks) / fs,
                   sig_filtered[fp_peaks],
                   color='#F44336', s=80, zorder=7,
                   marker='x', linewidths=2, label='False positive (FP)')

    # False negatives — orange diamonds
    if len(fn_peaks) > 0:
        ax.scatter(np.array(fn_peaks) / fs,
                   sig_filtered[fn_peaks],
                   color='#FF9800', s=80, zorder=7,
                   marker='D', label='False negative (FN)')

    ax.set_title(f'Record {record_name} — Detector Validation (first 5s)',
                 fontsize=12, fontweight='bold')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude (mV)')
    ax.legend(loc='upper right', fontsize=8)
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
    print("  DETECTOR VALIDATION")
    print("="*55)

    # Load data
    sig_n      = np.load(os.path.join(OUTPUT_DIR, 'ecg_normal_filtered.npy'))
    sig_a      = np.load(os.path.join(OUTPUT_DIR, 'ecg_af_filtered.npy'))
    rp_gt_n    = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_normal.npy'))
    rp_gt_a    = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_af.npy'))
    lbl_n      = np.load(os.path.join(OUTPUT_DIR, 'labels_normal.npy'))
    lbl_a      = np.load(os.path.join(OUTPUT_DIR, 'labels_af.npy'))
    rp_det_n   = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_detected_normal.npy'))
    rp_det_a   = np.load(os.path.join(OUTPUT_DIR, 'r_peaks_detected_af.npy'))

    # Filter ground truth to valid beats only
    gt_n = filter_ground_truth(rp_gt_n, lbl_n)
    gt_a = filter_ground_truth(rp_gt_a, lbl_a)

    print(f"\n  Record 100 — ground truth beats (valid): {len(gt_n)}")
    print(f"  Record 201 — ground truth beats (valid): {len(gt_a)}")

    # Match and compute metrics
    print("\n  Matching peaks...")
    tp_n, fp_n, fn_n, pairs_n = match_peaks(rp_det_n, gt_n)
    tp_a, fp_a, fn_a, pairs_a = match_peaks(rp_det_a, gt_a)

    se_n, pp_n = compute_metrics(tp_n, fp_n, fn_n)
    se_a, pp_a = compute_metrics(tp_a, fp_a, fn_a)

    # Print reports
    print_validation_report('100 (Normal)', tp_n, fp_n, fn_n, se_n, pp_n)
    print_validation_report('201 (AF)',     tp_a, fp_a, fn_a, se_a, pp_a)

    # Plots
    print("\n  Generating validation plots...")
    plot_validation(sig_n, rp_det_n, gt_n, pairs_n, '100',
                    save_path=os.path.join(OUTPUT_DIR,
                    'week2_validation_normal.png'))
    plot_validation(sig_a, rp_det_a, gt_a, pairs_a, '201',
                    save_path=os.path.join(OUTPUT_DIR,
                    'week2_validation_af.png'))

    print("\n" + "="*55)
    print("  VALIDATION COMPLETE")
    print("="*55)