// tb_fir_filter.sv
// ================
// Testbench for fir_filter.sv
// Reads test vectors from D:\Project_3\vectors\
// Applies input samples one per clock cycle
// Compares output against expected values
// Reports pass/fail count at end

`timescale 1ns/1ps

module tb_fir_filter;

    // ─────────────────────────────────────────────────────────────
    // SIGNALS
    // ─────────────────────────────────────────────────────────────
    logic        clk;
    logic        rst_n;
    logic        valid_in;
    logic signed [15:0] sample_in;
    logic        valid_out;
    logic signed [15:0] sample_out;

    // ─────────────────────────────────────────────────────────────
    // DUT INSTANTIATION
    // ─────────────────────────────────────────────────────────────
    fir_filter dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .valid_in   (valid_in),
        .sample_in  (sample_in),
        .valid_out  (valid_out),
        .sample_out (sample_out)
    );

    // ─────────────────────────────────────────────────────────────
    // CLOCK — 10ns period = 100 MHz
    // ─────────────────────────────────────────────────────────────
    initial clk = 0;
    always #5 clk = ~clk;

    // ─────────────────────────────────────────────────────────────
    // TEST VECTORS
    // ─────────────────────────────────────────────────────────────
    localparam N_VECTORS  = 1024;
    localparam TAPS       = 33;
    localparam TOLERANCE  = 2;    // ±2 LSB tolerance for rounding

    logic signed [15:0] in_vec  [0:N_VECTORS-1];
    logic signed [15:0] exp_vec [0:N_VECTORS-1];

    // ─────────────────────────────────────────────────────────────
    // VARIABLES
    // ─────────────────────────────────────────────────────────────
    integer i;
    integer pass_count;
    integer fail_count;
    integer diff;

    // File handles
    integer fd_in, fd_out;
    integer scan_ret;

    initial begin
        // Load test vectors using fscanf
        fd_in  = $fopen("../../vectors/fir_input.txt",  "r");
        fd_out = $fopen("../../vectors/fir_output.txt", "r");

        if (fd_in  == 0) $fatal(1, "Cannot open fir_input.txt");
        if (fd_out == 0) $fatal(1, "Cannot open fir_output.txt");

        for (i = 0; i < N_VECTORS; i++) begin
            scan_ret = $fscanf(fd_in,  "%d\n", in_vec[i]);
            scan_ret = $fscanf(fd_out, "%d\n", exp_vec[i]);
        end

        $fclose(fd_in);
        $fclose(fd_out);

        // Initialise
        rst_n      = 0;
        valid_in   = 0;
        sample_in  = 0;
        pass_count = 0;
        fail_count = 0;

        // Reset for 5 cycles
        repeat(5) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        $display("==============================================");
        $display("  FIR FILTER TESTBENCH");
        $display("==============================================");

        // Apply inputs
        for (i = 0; i < N_VECTORS; i++) begin
            @(posedge clk);
            valid_in  = 1;
            sample_in = in_vec[i];
        end

        // Flush pipeline — wait for last output
        valid_in = 0;
        repeat(TAPS + 5) @(posedge clk);

        $display("  Pass : %0d", pass_count);
        $display("  Fail : %0d", fail_count);
        $display("  Total: %0d", pass_count + fail_count);
        if (fail_count == 0)
            $display("  RESULT: ALL PASS ✓");
        else
            $display("  RESULT: FAILURES DETECTED ✗");
        $display("==============================================");
        $finish;
    end

    // ─────────────────────────────────────────────────────────────
    // OUTPUT CHECKER
    // ─────────────────────────────────────────────────────────────
    // Skip first TAPS-1 outputs (pipeline filling)
    integer out_idx;
    initial out_idx = 0;

    always @(posedge clk) begin
        if (valid_out) begin
            if (out_idx >= TAPS - 1) begin
                // Compare with tolerance
                diff = sample_out - exp_vec[out_idx - (TAPS-1)];
                if (diff < 0) diff = -diff;

                if (diff <= TOLERANCE)
                    pass_count++;
                else begin
                    fail_count++;
                    if (fail_count <= 5)  // print first 5 failures only
                        $display("  FAIL idx=%0d got=%0d exp=%0d diff=%0d",
                                 out_idx, sample_out,
                                 exp_vec[out_idx-(TAPS-1)], diff);
                end
            end
            out_idx++;
        end
    end

endmodule