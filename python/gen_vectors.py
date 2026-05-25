"""
gen_vectors.py
==============
ECG Accelerator Project — Week 2 Session 10
Generates test vectors for all RTL modules.

Test vectors are plain .txt files that Vivado testbenches read directly.
Format for each module:
  input_file.txt  : one input value per line
  output_file.txt : one expected output per line

Modules covered:
  1. FIR filter       : input=raw ECG samples, output=filtered samples
  2. Differentiator   : input=filtered samples, output=differentiated
  3. Squarer          : input=differentiated, output=squared
  4. MWI              : input=squared, output=integrated
  5. MAD classifier   : input=8 RR intervals, output=label + NV
"""

import numpy as np
import os

FS         = 360
VECTORS_DIR = r'D:\Project_3\vectors'
PYTHON_DIR  = r'D:\Project_3\python'
N_SAMPLES   = 1024      # number of samples per vector file
Q15_SCALE   = 32768     # Q1.15 scaling factor


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def to_q15(x):
    """Convert float array to Q1.15 integer array."""
    clipped = np.clip(x, -1.0, 0.99997)
    return np.round(clipped * Q15_SCALE).astype(np.int16)


def float_to_q15_scalar(x):
    """Convert single float to Q1.15 integer."""
    return int(round(np.clip(x, -1.0, 0.99997) * Q15_SCALE))


def save_vector(filename, data, fmt='%d'):
    """Save array to text file, one value per line."""
    path = os.path.join(VECTORS_DIR, filename)
    np.savetxt(path, data.astype(np.int32), fmt=fmt)
    print(f"  ✓ Saved {filename:45s} ({len(data)} lines)")


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 1 — FIR FILTER
# ─────────────────────────────────────────────────────────────────────────────

def gen_fir_vectors(ecg_raw, ecg_filtered, h):
    """
    FIR filter test vectors.

    Input  : raw ECG samples in Q1.15
    Output : filtered ECG samples in Q1.15

    Hardware computes:
      y[n] = h[0]*x[n] + h[1]*x[n-1] + ... + h[32]*x[n-32]
    All arithmetic in Q1.15 — each multiply needs >>15 shift.
    """
    print("\n  [1] FIR Filter vectors...")

    # Normalise raw ECG to Q1.15 range
    max_val = np.max(np.abs(ecg_raw))
    ecg_norm = ecg_raw / max_val  # now in [-1, +1]
    filt_norm = ecg_filtered / max_val

    # Convert to Q1.15
    ecg_q15  = to_q15(ecg_norm[:N_SAMPLES])
    filt_q15 = to_q15(filt_norm[:N_SAMPLES])

    save_vector('fir_input.txt',  ecg_q15)
    save_vector('fir_output.txt', filt_q15)

    # Also save filter coefficients in Q1.15
    h_q15 = to_q15(h)
    save_vector('fir_coeffs.txt', h_q15)


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 2 — DIFFERENTIATOR
# ─────────────────────────────────────────────────────────────────────────────

def gen_diff_vectors(ecg_filtered):
    """
    Differentiator test vectors.
    y[n] = (1/8)(2x[n] + x[n-1] - x[n-3] - 2x[n-4])

    Input  : filtered ECG in Q1.15
    Output : differentiated signal in Q1.15
    """
    print("\n  [2] Differentiator vectors...")

    from pan_tompkins import differentiate

    max_val  = np.max(np.abs(ecg_filtered))
    filt_norm = ecg_filtered / max_val
    diff      = differentiate(filt_norm)

    # Normalise diff to Q1.15
    max_diff = np.max(np.abs(diff)) + 1e-10
    diff_norm = diff / max_diff

    filt_q15 = to_q15(filt_norm[:N_SAMPLES])
    diff_q15 = to_q15(diff_norm[:N_SAMPLES])

    save_vector('diff_input.txt',  filt_q15)
    save_vector('diff_output.txt', diff_q15)


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 3 — SQUARER
# ─────────────────────────────────────────────────────────────────────────────

def gen_squarer_vectors(ecg_filtered):
    """
    Squarer test vectors.
    y[n] = x[n]²  (Q1.15 multiply with >>15 shift)

    Input  : differentiated signal in Q1.15
    Output : squared signal in Q1.15
    """
    print("\n  [3] Squarer vectors...")

    from pan_tompkins import differentiate, square

    max_val   = np.max(np.abs(ecg_filtered))
    filt_norm = ecg_filtered / max_val
    diff      = differentiate(filt_norm)
    max_diff  = np.max(np.abs(diff)) + 1e-10
    diff_norm = diff / max_diff
    sq        = square(diff_norm)

    diff_q15  = to_q15(diff_norm[:N_SAMPLES])
    sq_q15    = to_q15(sq[:N_SAMPLES])

    save_vector('squarer_input.txt',  diff_q15)
    save_vector('squarer_output.txt', sq_q15)


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 4 — MOVING WINDOW INTEGRATOR
# ─────────────────────────────────────────────────────────────────────────────

def gen_mwi_vectors(ecg_filtered):
    """
    MWI test vectors.
    y[n] = (x[n] + x[n-1] + ... + x[n-29]) / 30

    Input  : squared signal in Q1.15
    Output : integrated signal in Q1.15
    Hardware divides by 30 = multiplies by 1092 in Q1.15.
    """
    print("\n  [4] MWI vectors...")

    from pan_tompkins import differentiate, square, moving_window_integrate

    max_val   = np.max(np.abs(ecg_filtered))
    filt_norm = ecg_filtered / max_val
    diff      = differentiate(filt_norm)
    max_diff  = np.max(np.abs(diff)) + 1e-10
    diff_norm = diff / max_diff
    sq        = square(diff_norm)
    integ     = moving_window_integrate(sq)

    max_integ  = np.max(np.abs(integ)) + 1e-10
    integ_norm = integ / max_integ

    sq_q15    = to_q15(sq[:N_SAMPLES])
    integ_q15 = to_q15(integ_norm[:N_SAMPLES])

    save_vector('mwi_input.txt',  sq_q15)
    save_vector('mwi_output.txt', integ_q15)


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 5 — MAD CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

def gen_classifier_vectors(r_peaks_n, r_peaks_a):
    """
    MAD classifier test vectors.

    For each 8-beat window:
      Input  : 8 RR intervals in samples (integer)
      Output : label (01=Normal, 10=AF) + NV in Q1.15

    Generates 200 windows from each record — mix of Normal and AF.
    """
    print("\n  [5] MAD Classifier vectors...")

    from classifier import classify_window_q15, LABEL_NORMAL, LABEL_AF

    inputs  = []
    outputs = []

    for rp, expected_label in [(r_peaks_n, LABEL_NORMAL),
                                (r_peaks_a, LABEL_AF)]:
        rr = np.diff(rp).astype(np.int32)
        n_windows = min(200, len(rr) - 8)

        for i in range(n_windows):
            window = rr[i : i + 8]
            label, nv_q15 = classify_window_q15(window)

            # Input line: 8 RR values space separated
            inputs.append(' '.join(map(str, window)))
            # Output line: label nv_q15
            outputs.append(f"{label} {nv_q15}")

    # Save as text files
    in_path  = os.path.join(VECTORS_DIR, 'classifier_input.txt')
    out_path = os.path.join(VECTORS_DIR, 'classifier_output.txt')

    with open(in_path, 'w') as f:
        f.write('\n'.join(inputs))
    with open(out_path, 'w') as f:
        f.write('\n'.join(outputs))

    print(f"  ✓ Saved classifier_input.txt          "
          f"         ({len(inputs)} windows)")
    print(f"  ✓ Saved classifier_output.txt         "
          f"         ({len(outputs)} windows)")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("="*55)
    print("  TEST VECTOR GENERATION")
    print("="*55)

    os.makedirs(VECTORS_DIR, exist_ok=True)

    # Load data
    ecg_n      = np.load(os.path.join(PYTHON_DIR, 'ecg_normal.npy'))
    ecg_filt_n = np.load(os.path.join(PYTHON_DIR, 'ecg_normal_filtered.npy'))
    h          = np.load(os.path.join(PYTHON_DIR, 'fir_coefficients.npy'))
    rp_n       = np.load(os.path.join(PYTHON_DIR, 'r_peaks_detected_normal.npy'))
    rp_a       = np.load(os.path.join(PYTHON_DIR, 'r_peaks_detected_af.npy'))

    print(f"\n  Loaded all input data")

    # Generate vectors for each module
    gen_fir_vectors(ecg_n, ecg_filt_n, h)
    gen_diff_vectors(ecg_filt_n)
    gen_squarer_vectors(ecg_filt_n)
    gen_mwi_vectors(ecg_filt_n)
    gen_classifier_vectors(rp_n, rp_a)

    print(f"\n  All vectors saved to {VECTORS_DIR}")
    print("\n" + "="*55)
    print("  VECTOR GENERATION COMPLETE")
    print("="*55)