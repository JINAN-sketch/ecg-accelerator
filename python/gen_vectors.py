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

FS          = 360
VECTORS_DIR = r'D:\Project_3\vectors'
PYTHON_DIR  = r'D:\Project_3\python'
N_SAMPLES   = 1024
Q15_SCALE   = 32768


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def to_q15(x):
    """Convert float array to Q1.15 integer array."""
    clipped = np.clip(x, -1.0, 0.99997)
    return np.round(clipped * Q15_SCALE).astype(np.int16)


def save_vector(filename, data, fmt='%d'):
    """Save array to text file, one value per line."""
    path = os.path.join(VECTORS_DIR, filename)
    np.savetxt(path, data.astype(np.int32), fmt=fmt)
    print(f"  ✓ Saved {filename:45s} ({len(data)} lines)")


# ─────────────────────────────────────────────────────────────────────────────
# RTL-ACCURATE REFERENCE MODELS
# These match the exact integer arithmetic the hardware performs.
# Python float operations would give slightly different results.
# ─────────────────────────────────────────────────────────────────────────────

def fir_q15_reference(input_q15, h_q15):
    """
    Compute FIR output using exact integer arithmetic matching RTL.
    y[n] = sum(h[k] * x[n-k]) >> 15  for k=0..32
    Saturates to 16-bit at output.
    """
    n      = len(input_q15)
    output = np.zeros(n, dtype=np.int32)
    taps   = len(h_q15)
    for i in range(taps - 1, n):
        acc = 0
        for k in range(taps):
            acc += (int(input_q15[i - k]) * int(h_q15[k])) >> 15
        output[i] = int(np.clip(acc, -32768, 32767))
    return output


def diff_q15_reference(input_q15):
    """
    Differentiator: y[n] = (2x[n] + x[n-1] - x[n-3] - 2x[n-4]) / 8
    Division by 8 = arithmetic right shift 3.
    """
    n      = len(input_q15)
    output = np.zeros(n, dtype=np.int32)
    for i in range(4, n):
        val = (2 * int(input_q15[i])
               +   int(input_q15[i-1])
               -   int(input_q15[i-3])
               - 2*int(input_q15[i-4]))
        output[i] = int(np.clip(val >> 3, -32768, 32767))
    return output


def squarer_q15_reference(input_q15):
    """
    Squarer: y[n] = (x[n] * x[n]) >> 15
    Q1.15 multiply — 32-bit intermediate, shift right 15.
    """
    n      = len(input_q15)
    output = np.zeros(n, dtype=np.int32)
    for i in range(n):
        prod      = int(input_q15[i]) * int(input_q15[i])
        output[i] = int(np.clip(prod >> 15, -32768, 32767))
    return output


def mwi_q15_reference(input_q15, window=30):
    """
    Moving window integrator: y[n] = sum(x[n-k] for k=0..29) * 1092 >> 15
    1092 = round(1/30 * 32768) in Q1.15.
    """
    n         = len(input_q15)
    output    = np.zeros(n, dtype=np.int32)
    Q15_DIV30 = 1092
    for i in range(window - 1, n):
        window_sum = int(np.sum(input_q15[i - window + 1 : i + 1].astype(np.int32)))
        output[i]  = int(np.clip((window_sum * Q15_DIV30) >> 15, -32768, 32767))
    return output


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 1 — FIR FILTER
# ─────────────────────────────────────────────────────────────────────────────

def gen_fir_vectors(ecg_raw, h):
    """
    FIR filter test vectors.
    Output generated using exact RTL integer arithmetic.
    """
    print("\n  [1] FIR Filter vectors...")

    max_val  = np.max(np.abs(ecg_raw))
    ecg_norm = ecg_raw / max_val
    ecg_q15  = to_q15(ecg_norm[:N_SAMPLES])
    h_q15    = np.round(h * Q15_SCALE).astype(np.int32)

    filt_q15 = fir_q15_reference(ecg_q15, h_q15).astype(np.int16)

    save_vector('fir_input.txt',  ecg_q15)
    save_vector('fir_output.txt', filt_q15)
    save_vector('fir_coeffs.txt', h_q15.astype(np.int16))


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 2 — DIFFERENTIATOR
# ─────────────────────────────────────────────────────────────────────────────

def gen_diff_vectors(ecg_filtered):
    """
    Differentiator test vectors.
    Output generated using exact RTL integer arithmetic.
    """
    print("\n  [2] Differentiator vectors...")

    max_val   = np.max(np.abs(ecg_filtered))
    filt_norm = ecg_filtered / max_val
    filt_q15  = to_q15(filt_norm[:N_SAMPLES])
    diff_q15  = diff_q15_reference(filt_q15).astype(np.int16)

    save_vector('diff_input.txt',  filt_q15)
    save_vector('diff_output.txt', diff_q15)


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 3 — SQUARER
# ─────────────────────────────────────────────────────────────────────────────

def gen_squarer_vectors(ecg_filtered):
    """
    Squarer test vectors.
    Output generated using exact RTL integer arithmetic.
    """
    print("\n  [3] Squarer vectors...")

    max_val   = np.max(np.abs(ecg_filtered))
    filt_norm = ecg_filtered / max_val
    filt_q15  = to_q15(filt_norm[:N_SAMPLES])
    diff_q15  = diff_q15_reference(filt_q15).astype(np.int16)
    sq_q15    = squarer_q15_reference(diff_q15).astype(np.int16)

    save_vector('squarer_input.txt',  diff_q15)
    save_vector('squarer_output.txt', sq_q15)


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 4 — MOVING WINDOW INTEGRATOR
# ─────────────────────────────────────────────────────────────────────────────

def gen_mwi_vectors(ecg_filtered):
    """
    MWI test vectors.
    Output generated using exact RTL integer arithmetic.
    """
    print("\n  [4] MWI vectors...")

    max_val   = np.max(np.abs(ecg_filtered))
    filt_norm = ecg_filtered / max_val
    filt_q15  = to_q15(filt_norm[:N_SAMPLES])
    diff_q15  = diff_q15_reference(filt_q15).astype(np.int16)
    sq_q15    = squarer_q15_reference(diff_q15).astype(np.int16)
    mwi_q15   = mwi_q15_reference(sq_q15).astype(np.int16)

    save_vector('mwi_input.txt',  sq_q15)
    save_vector('mwi_output.txt', mwi_q15)


# ─────────────────────────────────────────────────────────────────────────────
# VECTOR 5 — MAD CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

def gen_classifier_vectors(r_peaks_n, r_peaks_a):
    """
    MAD classifier test vectors.
    Input : 8 RR intervals in samples
    Output: label (01=Normal, 10=AF) + NV in Q1.15
    """
    print("\n  [5] MAD Classifier vectors...")

    from classifier import classify_window_q15, LABEL_NORMAL, LABEL_AF

    inputs  = []
    outputs = []

    for rp, expected_label in [(r_peaks_n, LABEL_NORMAL),
                                (r_peaks_a, LABEL_AF)]:
        rr        = np.diff(rp).astype(np.int32)
        n_windows = min(200, len(rr) - 8)

        for i in range(n_windows):
            window        = rr[i : i + 8]
            label, nv_q15 = classify_window_q15(window)
            inputs.append(' '.join(map(str, window)))
            outputs.append(f"{label} {nv_q15}")

    in_path  = os.path.join(VECTORS_DIR, 'classifier_input.txt')
    out_path = os.path.join(VECTORS_DIR, 'classifier_output.txt')

    with open(in_path, 'w') as f:
        f.write('\n'.join(inputs))
    with open(out_path, 'w') as f:
        f.write('\n'.join(outputs))

    print(f"  ✓ Saved classifier_input.txt                   ({len(inputs)} windows)")
    print(f"  ✓ Saved classifier_output.txt                  ({len(outputs)} windows)")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("="*55)
    print("  TEST VECTOR GENERATION")
    print("="*55)

    os.makedirs(VECTORS_DIR, exist_ok=True)

    ecg_n      = np.load(os.path.join(PYTHON_DIR, 'ecg_normal.npy'))
    ecg_filt_n = np.load(os.path.join(PYTHON_DIR, 'ecg_normal_filtered.npy'))
    h          = np.load(os.path.join(PYTHON_DIR, 'fir_coefficients.npy'))
    rp_n       = np.load(os.path.join(PYTHON_DIR, 'r_peaks_detected_normal.npy'))
    rp_a       = np.load(os.path.join(PYTHON_DIR, 'r_peaks_detected_af.npy'))

    print(f"\n  Loaded all input data")

    gen_fir_vectors(ecg_n, h)
    gen_diff_vectors(ecg_filt_n)
    gen_squarer_vectors(ecg_filt_n)
    gen_mwi_vectors(ecg_filt_n)
    gen_classifier_vectors(rp_n, rp_a)

    print(f"\n  All vectors saved to {VECTORS_DIR}")
    print("\n" + "="*55)
    print("  VECTOR GENERATION COMPLETE")
    print("="*55)