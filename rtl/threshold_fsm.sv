`timescale 1ns/1ps

// threshold_fsm.sv
// ================
// Pan-Tompkins adaptive threshold R-peak detector
// Operates on MWI output (integrated signal)
//
// States:
//   IDLE       : waiting for signal to exceed threshold
//   RISING     : signal above threshold, tracking peak
//   PEAK       : peak found, output pulse, update thresholds
//   REFRACTORY : lockout for 72 cycles (200ms at 360Hz)
//
// Threshold update:
//   signal_level = 0.125 * peak + 0.875 * signal_level
//   threshold    = noise_level + 0.25 * (signal_level - noise_level)
//   noise_level  = 0.125 * current + 0.875 * noise_level (between detections)
//
// 0.125 = 1/8 = right shift 3
// 0.875 = 7/8 = value - value>>3
// 0.25  = 1/4 = right shift 2

module threshold_fsm (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        valid_in,
    input  logic signed [15:0] integrated,
    output logic        r_peak,        // high one cycle on R-peak detection
    output logic [15:0] r_peak_idx     // sample index of detected peak
);

    // ─────────────────────────────────────────────────────────────
    // PARAMETERS
    // ─────────────────────────────────────────────────────────────
    localparam REFRAC_PERIOD = 72;   // 200ms at 360 Hz — renamed to avoid
                                     // conflict with REFRACTORY state name

    // ─────────────────────────────────────────────────────────────
    // STATE ENCODING
    // ─────────────────────────────────────────────────────────────
    typedef enum logic [1:0] {
        IDLE       = 2'b00,
        RISING     = 2'b01,
        PEAK       = 2'b10,
        REFRACTORY = 2'b11
    } state_t;

    state_t state;

    // ─────────────────────────────────────────────────────────────
    // INTERNAL SIGNALS
    // ─────────────────────────────────────────────────────────────
    logic signed [15:0] signal_level;
    logic signed [15:0] noise_level;
    logic signed [15:0] threshold;
    logic signed [15:0] peak_val;
    logic        [15:0] sample_cnt;
    logic        [15:0] peak_sample;
    logic        [ 6:0] refrac_cnt;

    // Threshold arithmetic intermediates — declared at module level
    logic signed [15:0] sl_update;
    logic signed [15:0] nl_update;
    logic signed [15:0] thresh_update;
    logic signed [15:0] diff;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state        <= IDLE;
            signal_level <= 16'sd100;
            noise_level  <= 16'sd10;
            threshold    <= 16'sd25;
            peak_val     <= 16'sd0;
            sample_cnt   <= 16'd0;
            peak_sample  <= 16'd0;
            refrac_cnt   <= 7'd0;
            r_peak       <= 1'b0;
            r_peak_idx   <= 16'd0;
        end
        else begin
            r_peak     <= 1'b0;
            sample_cnt <= sample_cnt + 1;

            case (state)

                IDLE: begin
                    if (valid_in) begin
                        if ($signed(integrated) > $signed(threshold)) begin
                            peak_val    <= integrated;
                            peak_sample <= sample_cnt;
                            state       <= RISING;
                        end
                        else begin
                            nl_update   = noise_level
                                        - (noise_level >>> 3)
                                        + ($signed(integrated) >>> 3);
                            noise_level <= nl_update;

                            diff          = signal_level - noise_level;
                            thresh_update = noise_level + (diff >>> 2);
                            threshold    <= thresh_update;
                        end
                    end
                end

                RISING: begin
                    if (valid_in) begin
                        if ($signed(integrated) >= $signed(peak_val)) begin
                            peak_val    <= integrated;
                            peak_sample <= sample_cnt;
                        end
                        else begin
                            state <= PEAK;
                        end
                    end
                end

                PEAK: begin
                    r_peak     <= 1'b1;
                    r_peak_idx <= peak_sample;

                    sl_update    = signal_level
                                 - (signal_level >>> 3)
                                 + (peak_val >>> 3);
                    signal_level <= sl_update;

                    diff          = sl_update - noise_level;
                    thresh_update = noise_level + (diff >>> 2);
                    threshold    <= thresh_update;

                    refrac_cnt <= 7'd0;
                    state      <= REFRACTORY;
                end

                REFRACTORY: begin
                    if (refrac_cnt >= REFRAC_PERIOD - 1) begin
                        state <= IDLE;
                    end
                    else begin
                        refrac_cnt <= refrac_cnt + 1;
                    end
                end

            endcase
        end
    end

endmodule