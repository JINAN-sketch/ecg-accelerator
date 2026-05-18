# PROJECT 3 PROMPT — Paste this into a fresh Claude chat

You are an expert in VLSI design, digital signal processing, and algorithm-hardware co-design. You will help me build a complete RTL stream-processing accelerator for real-time ECG arrhythmia detection — from a Python algorithm baseline all the way to a fully verified synthesisable SystemVerilog implementation in Vivado — over 8 weeks. This is a serious resume project directly based on IEEE paper EPRO-VLSI-004: "Stream Processing Architectures for Continuous ECG Monitoring Using Subsampling-Based Classifiers."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABOUT ME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- B.E. Electrical and Electronics Engineering, BITS Pilani, 2027 (CGPA 8.62)
- Courses completed: Analog & Digital VLSI Design, Verilog Programming, Reconfigurable Computing, Digital Design, Signals & Systems, Communication Systems, Semiconductor Devices, Control Systems
- Previous Verilog/SystemVerilog project: Full VGA display pipeline in Vivado — custom HSYNC/VSYNC, BRAM-optimised framebuffer, pixel-level rendering. I am comfortable with Vivado simulation and the waveform viewer.
- I also understand FIR filters, convolution, and basic DSP from Signals & Systems
- Programming: Python (comfortable), C (bare-metal microcontroller level), Verilog (competent)
- Internship: Siemens — PIC18 debugging, Python/C# scripting
- Tools: Vivado 2023.x WebPACK (free), Python 3.x (numpy, scipy, matplotlib), Git. NO physical FPGA required — simulation only.
- Fixed-point arithmetic: I understand floating point but have not implemented fixed-point hardware before. Teach me thoroughly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT WE ARE BUILDING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A full algorithm-hardware co-designed RTL accelerator that processes a
continuous ECG data stream and detects atrial fibrillation (AF) vs normal
sinus rhythm in real time. The project has two phases:

PHASE 1 — Python (Weeks 1–3):
  Design, validate, and characterise the detection algorithm entirely in
  floating-point Python. This gives us a golden reference model.
  At the end of Phase 1 we convert all coefficients and thresholds to
  16-bit fixed-point (Q1.15 format) and verify accuracy is preserved.

PHASE 2 — SystemVerilog (Weeks 4–8):
  Implement the exact same pipeline as synthesisable RTL. Use the Python
  model to generate test vectors (input samples + expected output labels).
  Simulate the RTL against those vectors in Vivado. Finally, run Vivado
  synthesis to get resource usage and critical path delay.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALGORITHM PIPELINE SPECIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INPUT:
  - 16-bit signed fixed-point ECG samples
  - Sample rate: 360 Hz (MIT-BIH Arrhythmia Database standard)
  - Amplitude range: ±32767 (full Q1.15 range)

STAGE 1 — FIR BANDPASS FILTER:
  Purpose: Remove baseline wander (< 0.5 Hz) and high-frequency noise (> 40 Hz)
  Specification:
    - Type: Linear-phase FIR (symmetric coefficients → zero phase distortion)
    - Passband: 0.5 Hz – 40 Hz
    - Filter order: 32 taps (33 coefficients, odd-length for symmetry)
    - Window: Hamming window
    - Coefficients: computed in Python using scipy.signal.firwin, then
                    quantised to Q1.15 (16-bit signed fixed-point)
  Hardware:
    - Transposed direct-form II FIR (pipeline-friendly: no long delay chain)
    - Each tap: one 16×16 multiply → 32-bit product → accumulate
    - Output: 32-bit accumulator, truncated to 16-bit after scaling
    - Latency: 33 clock cycles (one per tap in the transposed form)

STAGE 2 — R-PEAK DETECTOR (Pan-Tompkins algorithm, hardware-adapted):
  Purpose: Find the R-peak (tallest spike) of each QRS complex
  Steps:
    Step 2a — Derivative: highlights the steep QRS slope
      y[n] = (1/8)(2x[n] + x[n-1] − x[n-3] − 2x[n-4])
      Hardware: 5-tap FIR with coefficients {2, 1, 0, -1, -2}/8

    Step 2b — Squaring: amplifies large values, suppresses small
      y[n] = x[n]^2
      Hardware: 16×16 unsigned multiply → keep upper 16 bits (shift right 16)

    Step 2c — Moving window integrator: smooths the signal
      y[n] = (1/N) * Σ x[n-k] for k=0..N-1,  N=30 samples (~83ms at 360Hz)
      Hardware: sliding sum with a 30-element shift register, divide by 30
               (implemented as multiply by 1/30 ≈ 2185 in Q15, then shift)

    Step 2d — Threshold detector + refractory period:
      - Adaptive threshold: threshold = 0.5 × running_max (updated each beat)
      - R-peak detected when integrator output crosses threshold
      - Refractory period: 200ms = 72 samples — ignore further crossings
      Hardware: comparator + counter for refractory period + threshold register

STAGE 3 — RR-INTERVAL CALCULATOR:
  Purpose: Measure time between consecutive R-peaks
  Hardware:
    - 16-bit cycle counter, clears on each R-peak detection
    - On R-peak: latch counter value as RR_interval, reset counter
    - Output: RR_interval in samples (divide by 360 for seconds)
    - Store last 8 RR intervals in a shift register for Stage 4

STAGE 4 — RHYTHM CLASSIFIER FSM:
  Purpose: Decide Normal vs AF based on RR interval irregularity
  Algorithm:
    - Compute mean RR over last 8 beats: mean_RR = Σ RR[i] / 8
    - Compute mean absolute deviation: MAD = Σ |RR[i] - mean_RR| / 8
    - Normalised variability: NV = MAD / mean_RR  (fixed-point division)
    - Threshold: if NV > THRESH (0.08 → 2621 in Q1.15), classify as AF
  Hardware:
    - Accumulator for sum of RR (last 8)
    - Accumulator for sum of absolute deviations
    - Fixed-point divider (non-restoring, 16 cycles latency)
    - Comparator with programmable threshold register
    - Output: 2-bit classification {00=unknown, 01=normal, 10=AF, 11=noisy}

OUTPUT:
  - classification[1:0]: valid 1 cycle after each 8th RR interval is computed
  - beat_count[15:0]: total beats processed
  - rr_latest[15:0]: most recent RR interval

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FILE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ecg_accelerator/
├── python/
│   ├── week1_load_and_explore.py    # Data loading + visualisation
│   ├── week2_algorithm.py           # FIR filter + Pan-Tompkins
│   ├── week3_classifier.py          # RR analysis + AF detection
│   ├── week3_fixed_point.py         # Floating→fixed conversion + accuracy check
│   └── export_test_vectors.py       # Export .txt files for RTL testbench
├── rtl/
│   ├── fir_filter.sv                # 33-tap bandpass FIR (transposed form)
│   ├── derivative_filter.sv         # 5-tap Pan-Tompkins derivative
│   ├── squaring_unit.sv             # 16-bit squarer
│   ├── moving_avg.sv                # 30-sample moving window integrator
│   ├── rpeak_detector.sv            # Threshold + refractory FSM
│   ├── rr_calculator.sv             # RR interval counter + shift register
│   ├── classifier_fsm.sv            # Rhythm classifier with fixed-point divider
│   ├── fixed_point_div.sv           # Non-restoring fixed-point divider
│   └── ecg_top.sv                   # Top-level: wires all stages
├── tb/
│   ├── tb_fir_filter.sv             # FIR unit testbench
│   ├── tb_rpeak.sv                  # R-peak detector testbench
│   ├── tb_classifier.sv             # Classifier FSM testbench
│   └── tb_ecg_top.sv                # Full system testbench (uses vector files)
├── vectors/
│   ├── ecg_normal_samples.txt       # Generated by Python
│   ├── ecg_af_samples.txt
│   ├── expected_normal_labels.txt
│   └── expected_af_labels.txt
└── syn/
    └── synth_report.txt             # Vivado synthesis results

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8-WEEK PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Week 1 (Python): Load MIT-BIH arrhythmia data using the wfdb library.
  Plot raw ECG for normal (record 100) and AF (record 201). Annotate R-peaks
  from the ground truth labels. Plot RR tachogram for both. Print statistics:
  mean RR, RR std dev, beat count, label distribution. Understand exactly what
  makes AF different from normal in the signal domain.
  NOTE: If PhysioNet is inaccessible (network restrictions), generate
  synthetic MIT-BIH-faithful signals — the code must work either way.

Week 2 (Python): Implement the full Pan-Tompkins pipeline in Python.
  Step by step: FIR bandpass → derivative → squaring → moving average →
  threshold + refractory. Plot each intermediate stage for one 10-second
  segment. Measure R-peak detection sensitivity and positive predictive value
  on 5 MIT-BIH records. Target: >95% sensitivity.

Week 3 (Python): Build the RR-interval classifier. Extract RR intervals
  from detected peaks. Compute MAD-based normalised variability. Tune the
  threshold on 10 records. Report accuracy, sensitivity, specificity.
  Then: convert all coefficients (FIR taps, derivative coefficients, moving
  average weight, classifier threshold) to Q1.15 fixed-point. Verify that
  fixed-point Python implementation matches floating-point to within 2%
  accuracy. Export ECG sample vectors and expected labels as text files.

Week 4 (RTL): Implement fir_filter.sv — 33-tap transposed direct-form FIR.
  Ports: clk, rst, sample_in[15:0], valid_in, sample_out[15:0], valid_out.
  Use generate loops for tap instantiation. Fully pipelined: accepts one
  sample per clock. Unit testbench: apply impulse input, verify output matches
  Python-computed impulse response (loaded from a vector file).

Week 5 (RTL): Implement derivative_filter.sv, squaring_unit.sv, moving_avg.sv.
  Chain them together in a test. Implement rpeak_detector.sv (threshold FSM
  with refractory period counter). Testbench: feed filtered ECG samples,
  verify R-peak pulses match Python ground truth positions ±2 samples.

Week 6 (RTL): Implement rr_calculator.sv (cycle counter, 8-element RR shift
  register). Implement fixed_point_div.sv (16-cycle non-restoring divider —
  we will build this step by step). Implement classifier_fsm.sv.
  Unit test each module.

Week 7 (RTL): Build ecg_top.sv — wire all stages. Build tb_ecg_top.sv:
  reads ecg_normal_samples.txt and ecg_af_samples.txt, streams samples into
  the design at 360 Hz (simulated), collects classification outputs, compares
  to expected_*_labels.txt, prints pass/fail summary with accuracy metric.

Week 8 (RTL): Fix any classification errors found in Week 7. Run Vivado
  synthesis targeting Artix-7 (xc7a35t). Record: LUT count, FF count,
  DSP48 count, BRAM count, critical path delay (ns), max frequency (MHz).
  Compute throughput: classifications per second. Write final README.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW YOU MUST HELP ME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. PYTHON WEEKS: Give me complete, runnable Python code. Every function
   fully implemented. All imports at the top. Matplotlib plots saved to file
   (not just shown). Numerical output printed clearly with labels and units.

2. RTL WEEKS: Give me complete, synthesisable SystemVerilog. No pseudocode.
   Every port declared. Every always_ff and always_comb block fully written.
   Use logic throughout (not reg/wire). Use always_ff for flip-flops and
   always_comb for combinational. Comment every non-obvious line.

3. FIXED-POINT: Every time we use fixed-point arithmetic explain:
   - What Q-format we are using and why
   - Where overflow can occur and how we prevent it
   - The hardware cost (how many bits wide the intermediate product is)
   - How we truncate vs round and what error this introduces

4. CONNECTING PYTHON TO RTL: After Week 3, always tell me:
   - What the Python golden model predicts for a given input
   - What the RTL should produce for the same input
   - How to compare them (which signals to watch in simulation)

5. VIVADO GUIDANCE: For every RTL module, give me:
   - The Vivado TCL commands to add all source files and run simulation
   - Which signals to add to the waveform viewer
   - What correct waveforms look like described in words
   - How to use Vivado's built-in assertions panel

6. DEBUGGING: When I paste simulation output that doesn't match Python:
   - Identify the first cycle where divergence occurs
   - Trace back which module produced the wrong value
   - Give me the corrected RTL

7. At the start of each week: one-paragraph recap of current state,
   what we add this week, and how it connects to the full system.

8. Interview prep: after each major component, 2–3 questions a TI or
   ST Microelectronics ASIC engineer would ask, with full answers.
   (e.g. "Why transposed form FIR?", "How does Pan-Tompkins handle noise?",
   "What is the area-latency tradeoff in your fixed-point divider?")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESUME TARGET LINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Algorithm-hardware co-designed RTL stream-processing accelerator for real-time
ECG arrhythmia detection in SystemVerilog (Vivado): 33-tap fixed-point FIR
bandpass filter, Pan-Tompkins R-peak detector, RR-interval classifier FSM;
Python golden model validated on MIT-BIH dataset; synthesis report on Artix-7
shows [X] LUTs, [Y] DSPs, [Z] MHz maximum frequency."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
START NOW — WEEK 1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Begin Week 1. Give me the complete week1_load_and_explore.py. It must:

1. Try to load real MIT-BIH records 100 (normal) and 201 (AF) using wfdb.
   If PhysioNet download fails for any reason (network restrictions in the
   environment), AUTOMATICALLY fall back to generating synthetic MIT-BIH-
   faithful signals using the mathematical PQRST model. The code must work
   in both cases without any manual intervention. Print clearly which mode
   is running: "Using real MIT-BIH data" or "Using synthetic MIT-BIH replica".

2. Print a full statistical summary for both records:
   - Sample count, duration in seconds
   - Beat count and label distribution (N, A, V, etc.)
   - Mean RR interval in milliseconds
   - RR standard deviation in milliseconds
   - Min and max RR
   - Coefficient of variation of RR (std/mean × 100%)
   - Explain in a comment why CoV is the key feature for AF detection

3. Generate and save a 3-row × 2-column figure (week1_ecg_analysis.png):
   - Row 1: 10-second raw ECG with R-peak markers for both records
   - Row 2: 3-beat zoom with PQRST component labels on the first beat
   - Row 3: RR interval tachogram (ms vs beat number) with mean ± 1σ shading
   All axes labelled with units. Tight layout. DPI=150.

4. Save numpy arrays for Week 2:
   ecg_normal.npy, ecg_af.npy, r_peaks_normal.npy, r_peaks_af.npy,
   labels_normal.npy, labels_af.npy

5. Explain in comments throughout the code (not just here at the end):
   - What atrial fibrillation looks like electrically in the heart
   - Why the P-wave disappears in AF and what replaces it (f-waves)
   - Why RR irregularity is the primary computational feature we will
     implement in hardware, and not the P-wave shape (which would require
     much more complex hardware)
   - The clinical threshold: RR CoV > 8% is considered AF

6. After the code, give me 2 interview questions an Analog Devices or TI
   ASIC engineer would ask about this stage with full answers.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXECUTION PLAN — SEQUENTIAL, ONE PROJECT AT A TIME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is the FIRST of three sequential projects done one after the other
(P3 → P2 → P1). I am doing them sequentially, not in parallel, so this
project gets my full focus. I have 6–7 hours per day before 4pm. Weekends
are fully free. LeetCode happens at 4pm daily and is separate.

THIS PROJECT: 3.5 weeks total. Hard cutoff at end of week 3.5 — whatever
is done gets documented and pushed to GitHub, then I move to Project 2.

WEEKLY TARGETS (compact — I must hit these to stay on schedule):

  Week 1 target:
    week1_load_and_explore.py fully working. MIT-BIH data loaded (real or
    synthetic fallback — code handles both automatically). 3×2 plot saved.
    Statistical summary printed: mean RR, RR std, CoV for both records.
    numpy arrays saved for week 2. I understand clinically what AF looks
    like and why RR irregularity is the hardware-implementable feature.

  Week 2 target:
    week2_algorithm.py fully working. Full Pan-Tompkins pipeline in Python:
    FIR bandpass → derivative → squaring → moving average → threshold +
    refractory. Every intermediate stage plotted. R-peak detection
    sensitivity >95% on at least 5 MIT-BIH records. I can explain every
    step in signal processing terms.

  Week 3 target:
    week3_classifier.py: MAD-based AF classifier, tuned threshold, accuracy
    / sensitivity / specificity measured and logged.
    week3_fixed_point.py: all coefficients converted to Q1.15. Fixed-point
    Python matches float within 2% accuracy.
    export_test_vectors.py: ECG sample .txt files and expected label .txt
    files exported and ready for RTL testbench.
    fir_filter.sv: 33-tap transposed-form FIR in SystemVerilog. tb_fir_filter.sv
    passes impulse response test vs Python golden values.

  Week 3.5 target (HARD CUTOFF — move to P2 regardless):
    All remaining RTL modules completed: derivative_filter.sv,
    squaring_unit.sv, moving_avg.sv, rpeak_detector.sv, rr_calculator.sv,
    fixed_point_div.sv, classifier_fsm.sv, ecg_top.sv.
    tb_ecg_top.sv streams test vectors, compares output to Python labels,
    prints pass/fail + accuracy.
    Vivado synthesis run on Artix-7 (xc7a35t) — LUT/DSP/FF/freq recorded.
    GitHub README written with: architecture diagram, Python accuracy
    results, RTL simulation screenshot, synthesis numbers, resume bullet.
    PROJECT COMPLETE. Hard stop.

HOW TO USE THESE TARGETS WITH ME (Claude):
  At the start of each week, tell me: "Starting week X of Project 3."
  I will recap what we built last week, state exactly what we are building
  this week, and begin with the first complete piece of code immediately.
  I will not move to the next week's content until the current week's
  target deliverable is confirmed working. If we are running behind, I
  will tell you honestly and suggest what to cut without breaking the
  core project.
