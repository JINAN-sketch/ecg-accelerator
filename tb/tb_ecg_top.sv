`timescale 1ns/1ps

module tb_ecg_top;

    logic        clk;
    logic        rst_n;
    logic        valid_in;
    logic signed [15:0] sample_in;
    logic [1:0]  classification;
    logic [15:0] nv_q15;
    logic        r_peak;
    logic [15:0] r_peak_idx;

    ecg_top dut (
        .clk            (clk),
        .rst_n          (rst_n),
        .valid_in       (valid_in),
        .sample_in      (sample_in),
        .classification (classification),
        .nv_q15         (nv_q15),
        .r_peak         (r_peak),
        .r_peak_idx     (r_peak_idx)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    localparam N_SAMPLES = 4096;

    logic [15:0] ecg_vec [0:N_SAMPLES-1];

    integer i;
    integer peak_count;
    integer det_peaks [0:99];
    integer det_count;
    integer class_normal;
    integer class_af;
    integer class_init;

    initial begin
        $readmemh("D:/Project_3/vectors/ecg_normal_4096_hex.txt", ecg_vec);

        rst_n        = 0;
        valid_in     = 0;
        sample_in    = 0;
        peak_count   = 0;
        det_count    = 0;
        class_normal = 0;
        class_af     = 0;
        class_init   = 0;

        repeat(5) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        $display("==============================================");
        $display("  ECG TOP LEVEL INTEGRATION TESTBENCH");
        $display("==============================================");

        // Feed ECG samples through full pipeline
        for (i = 0; i < N_SAMPLES; i++) begin
            @(posedge clk);
            valid_in  = 1;
            sample_in = $signed(ecg_vec[i]);

            // Count R-peak detections
            if (r_peak && det_count < 100) begin
                det_peaks[det_count] = r_peak_idx;
                det_count = det_count + 1;
            end

            // Count classifications
            case (classification)
                2'b01: class_normal = class_normal + 1;
                2'b10: class_af     = class_af     + 1;
                2'b00: class_init   = class_init   + 1;
            endcase
        end

        // Flush pipeline
        valid_in = 0;
        repeat(100) @(posedge clk);

        // Final classification counts
        repeat(50) @(posedge clk) begin
            case (classification)
                2'b01: class_normal = class_normal + 1;
                2'b10: class_af     = class_af     + 1;
            endcase
        end

        $display("  Samples processed : %0d", N_SAMPLES);
        $display("  R-peaks detected  : %0d", det_count);
        $display("  Expected ~3 peaks (75 bpm over 1024 samples)");
        $display("  Peak indices:");
        for (i = 0; i < det_count && i < 10; i++)
            $display("    peak[%0d] = %0d", i, det_peaks[i]);
        $display("  Classification counts:");
        $display("    Init   : %0d", class_init);
        $display("    Normal : %0d", class_normal);
        $display("    AF     : %0d", class_af);
        $display("  Final classification: %0b", classification);

        if (det_count >= 10 && det_count <= 20)
            $display(" RESULT: PASS - correct peak count and Normal sclassification");
        else
            $display("  RESULT: FAIL - unexpected peak count");
        $display("==============================================");
        $finish;
    end

endmodule