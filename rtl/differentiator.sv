`timescale 1ns/1ps

// differentiator.sv
// =================
// Pan-Tompkins derivative filter
// y[n] = (2x[n] + x[n-1] - x[n-3] - 2x[n-4]) >> 3
// Division by 8 = arithmetic right shift 3
// 4-sample shift register
//
// Interface:
//   clk       : system clock (100 MHz)
//   rst_n     : active-low synchronous reset
//   valid_in  : high one cycle when input is valid
//   x_in      : Q1.15 signed input sample
//   valid_out : high one cycle when output is valid
//   y_out     : Q1.15 signed differentiated output

module differentiator (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        valid_in,
    input  logic signed [15:0] x_in,
    output logic        valid_out,
    output logic signed [15:0] y_out
);

    // ─────────────────────────────────────────────────────────────
    // 4-sample shift register
    // sr[0] = x[n-1], sr[1] = x[n-2], sr[2] = x[n-3], sr[3] = x[n-4]
    // (after clock edge — during computation sr holds OLD values)
    // ─────────────────────────────────────────────────────────────
    logic signed [15:0] sr [0:3];

    // 19-bit accumulator — wide enough for:
    // max value = 2*32767 + 32767 + 32767 + 2*32767 = 196602 < 2^18
    // so 19 bits (signed) is sufficient
    logic signed [18:0] acc;
    logic signed [18:0] shifted;
    integer k;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (k = 0; k < 4; k++)
                sr[k] <= 16'sd0;
            valid_out <= 1'b0;
            y_out     <= 16'sd0;
        end
        else if (valid_in) begin
            // Shift register update (non-blocking — takes effect end of time step)
            sr[0] <= x_in;
            sr[1] <= sr[0];
            sr[2] <= sr[1];
            sr[3] <= sr[2];

            // Compute differentiation using:
            //   x[n]   = x_in         (current input this cycle)
            //   x[n-1] = sr[0]        (OLD value — not yet updated)
            //   x[n-3] = sr[2]        (OLD value)
            //   x[n-4] = sr[3]        (OLD value)
            //
            // Sign extend each 16-bit value to 19-bit using replication:
            //   {{3{x[15]}}, x} extends sign bit 3 times
            acc = ({{3{x_in[15]}},  x_in}  <<< 1)   // 2 * x[n]
                + {{3{sr[0][15]}},  sr[0]}            // + x[n-1]
                - {{3{sr[2][15]}},  sr[2]}            // - x[n-3]
                - ({{3{sr[3][15]}}, sr[3]} <<< 1);    // - 2 * x[n-4]

            // Divide by 8 = arithmetic right shift 3
            shifted = acc >>> 3;

            // Saturate to 16-bit output
            if      (shifted > 19'sd32767)  y_out <= 16'sd32767;
            else if (shifted < -19'sd32768) y_out <= -16'sd32768;
            else                            y_out <= shifted[15:0];

            valid_out <= 1'b1;
        end
        else begin
            valid_out <= 1'b0;
        end
    end

endmodule