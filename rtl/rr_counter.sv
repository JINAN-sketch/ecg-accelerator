`timescale 1ns/1ps

// rr_counter.sv
// =============
// Measures RR intervals in samples between consecutive R-peak detections
// Counts clock cycles between r_peak pulses
// Outputs RR interval when new R-peak detected
//
// Interface:
//   clk        : system clock
//   rst_n      : active-low reset
//   r_peak     : high one cycle on R-peak detection (from threshold_fsm)
//   rr_valid   : high one cycle when new RR interval ready
//   rr_interval: RR interval in samples (16-bit)

module rr_counter (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        r_peak,
    output logic        rr_valid,
    output logic [15:0] rr_interval
);

    logic [15:0] counter;
    logic        first_peak;   // ignore first RR (no previous peak yet)

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            counter     <= 16'd0;
            rr_valid    <= 1'b0;
            rr_interval <= 16'd0;
            first_peak  <= 1'b1;
        end
        else begin
            rr_valid <= 1'b0;    // default

            if (r_peak) begin
                if (!first_peak) begin
                    rr_interval <= counter;
                    rr_valid    <= 1'b1;
                end
                first_peak <= 1'b0;
                counter    <= 16'd0;
            end
            else begin
                // Increment counter — saturate at 65535 to prevent overflow
                if (counter < 16'hFFFF)
                    counter <= counter + 1;
            end
        end
    end

endmodule