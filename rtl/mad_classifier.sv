`timescale 1ns/1ps

// mad_classifier.sv
// =================
// MAD-based AF classifier
// Collects 8 RR intervals, computes NV = MAD/mean_RR in Q1.15
// Compares against threshold 2621 (= 0.08 in Q1.15)
//
// Key fix: computation uses the NEW buffer state explicitly
// (rr_interval for position 0, rr_buf[0..6] for positions 1..7)
// This avoids the non-blocking assignment timing issue.
//
// Output encoding:
//   2'b00 = initialising (fewer than 8 beats)
//   2'b01 = Normal
//   2'b10 = AF

module mad_classifier (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        rr_valid,
    input  logic [15:0] rr_interval,
    output logic [1:0]  classification,
    output logic [15:0] nv_q15
);

    localparam WINDOW    = 8;
    localparam THRESHOLD = 16'd2621;

    // 7-deep buffer (position 1..7 of the 8-beat window)
    // Position 0 is always rr_interval (current input)
    logic [15:0] rr_buf [0:WINDOW-2];   // holds x[n-1] through x[n-7]

    logic [3:0] fill_cnt;

    // Arithmetic intermediates
    logic [18:0] rr_sum;
    logic [15:0] mean_rr;
    logic [18:0] dev_sum;
    logic [15:0] mad;
    logic [30:0] nv_num;
    logic [15:0] nv_result;
    logic [15:0] abs_dev;
    integer k;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (k = 0; k < WINDOW-1; k++)
                rr_buf[k] <= 16'd0;
            fill_cnt       <= 4'd0;
            classification <= 2'b00;
            nv_q15         <= 16'd0;
        end
        else if (rr_valid) begin
            // Shift register — rr_buf[0] gets current rr_interval
            // rr_buf[k] gets rr_buf[k-1] (old value)
            rr_buf[0] <= rr_interval;
            for (k = 1; k < WINDOW-1; k++)
                rr_buf[k] <= rr_buf[k-1];

            // Track fill count
            if (fill_cnt < WINDOW)
                fill_cnt <= fill_cnt + 1;

            // Classify when window has at least 8 values
            // Compute on NEW state: rr_interval + old rr_buf[0..6]
            if (fill_cnt >= WINDOW - 1) begin

                // Step 1: sum using new buffer state
                // new_buf[0] = rr_interval
                // new_buf[1..7] = rr_buf[0..6] (old values, not yet shifted)
                rr_sum = {3'b000, rr_interval};
                for (k = 0; k < WINDOW-1; k++)
                    rr_sum = rr_sum + {3'b000, rr_buf[k]};

                // Step 2: mean = sum >> 3
                mean_rr = rr_sum[18:3];

                // Step 3: absolute deviation for rr_interval
                if (rr_interval >= mean_rr)
                    abs_dev = rr_interval - mean_rr;
                else
                    abs_dev = mean_rr - rr_interval;
                dev_sum = {3'b000, abs_dev};

                // Step 3 cont: absolute deviations for rr_buf[0..6]
                for (k = 0; k < WINDOW-1; k++) begin
                    if (rr_buf[k] >= mean_rr)
                        abs_dev = rr_buf[k] - mean_rr;
                    else
                        abs_dev = mean_rr - rr_buf[k];
                    dev_sum = dev_sum + {3'b000, abs_dev};
                end

                // Step 4: MAD = dev_sum >> 3
                mad = dev_sum[18:3];

                // Step 5: NV = (mad << 15) / mean_rr
                if (mean_rr > 0) begin
                    nv_num    = {mad, 15'b0};
                    nv_result = nv_num / mean_rr;
                end
                else
                    nv_result = 16'd0;

                nv_q15 <= nv_result;

                // Step 6: classify
                if (nv_result > THRESHOLD)
                    classification <= 2'b10;  // AF
                else
                    classification <= 2'b01;  // Normal
            end
        end
    end

endmodule