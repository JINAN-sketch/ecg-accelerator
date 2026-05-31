`timescale 1ns/1ps

// ecg_top.sv
// ==========
// ECG AF Classifier — Top Level Integration
// Connects all modules in pipeline order:
//
//   sample_in → fir_filter → differentiator → squarer → mwi
//             → threshold_fsm → rr_counter → mad_classifier
//             → classification[1:0]
//
// All modules share single clock domain (clk)
// Valid signal propagates through pipeline
// Classification output:
//   2'b00 = initialising
//   2'b01 = Normal sinus rhythm
//   2'b10 = Atrial Fibrillation

module ecg_top (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        valid_in,
    input  logic signed [15:0] sample_in,
    output logic [1:0]  classification,
    output logic [15:0] nv_q15,
    output logic        r_peak,
    output logic [15:0] r_peak_idx
);

    // ─────────────────────────────────────────────────────────────
    // INTER-MODULE SIGNALS
    // ─────────────────────────────────────────────────────────────

    // FIR filter output
    logic        fir_valid;
    logic signed [15:0] fir_out;

    // Differentiator output
    logic        diff_valid;
    logic signed [15:0] diff_out;

    // Squarer output
    logic        sq_valid;
    logic signed [15:0] sq_out;

    // MWI output
    logic        mwi_valid;
    logic signed [15:0] mwi_out;

    // Threshold FSM output
    logic        r_peak_int;
    logic [15:0] r_peak_idx_int;

    // RR counter output
    logic        rr_valid;
    logic [15:0] rr_interval;

    // ─────────────────────────────────────────────────────────────
    // MODULE INSTANTIATIONS
    // ─────────────────────────────────────────────────────────────

    // Stage 1: FIR lowpass filter (40 Hz cutoff)
    fir_filter u_fir (
        .clk        (clk),
        .rst_n      (rst_n),
        .valid_in   (valid_in),
        .sample_in  (sample_in),
        .valid_out  (fir_valid),
        .sample_out (fir_out)
    );

    // Stage 2: Pan-Tompkins differentiation
    differentiator u_diff (
        .clk       (clk),
        .rst_n     (rst_n),
        .valid_in  (fir_valid),
        .x_in      (fir_out),
        .valid_out (diff_valid),
        .y_out     (diff_out)
    );

    // Stage 3: Squarer
    squarer u_sq (
        .clk       (clk),
        .rst_n     (rst_n),
        .valid_in  (diff_valid),
        .x_in      (diff_out),
        .valid_out (sq_valid),
        .y_out     (sq_out)
    );

    // Stage 4: Moving window integrator
    mwi u_mwi (
        .clk       (clk),
        .rst_n     (rst_n),
        .valid_in  (sq_valid),
        .x_in      (sq_out),
        .valid_out (mwi_valid),
        .y_out     (mwi_out)
    );

    // Stage 5: Adaptive threshold R-peak detector
    threshold_fsm u_thresh (
        .clk        (clk),
        .rst_n      (rst_n),
        .valid_in   (mwi_valid),
        .integrated (mwi_out),
        .r_peak     (r_peak_int),
        .r_peak_idx (r_peak_idx_int)
    );

    // Stage 6: RR interval counter
    rr_counter u_rr (
        .clk         (clk),
        .rst_n       (rst_n),
        .r_peak      (r_peak_int),
        .rr_valid    (rr_valid),
        .rr_interval (rr_interval)
    );

    // Stage 7: MAD classifier
    mad_classifier u_mad (
        .clk            (clk),
        .rst_n          (rst_n),
        .rr_valid       (rr_valid),
        .rr_interval    (rr_interval),
        .classification (classification),
        .nv_q15         (nv_q15)
    );

    // Route R-peak signals to top level for monitoring
    assign r_peak     = r_peak_int;
    assign r_peak_idx = r_peak_idx_int;

endmodule