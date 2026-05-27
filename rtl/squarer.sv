`timescale 1ns/1ps

// squarer.sv
// ==========
// Pan-Tompkins squarer
// y[n] = x[n]^2 in Q1.15
// 16-bit × 16-bit → 32-bit product → arithmetic right shift 15 → 16-bit
//
// Note: output is always non-negative (x^2 >= 0)
// Saturation kept for consistency with pipeline
//
// Interface:
//   clk       : system clock (100 MHz)
//   rst_n     : active-low synchronous reset
//   valid_in  : high one cycle when input is valid
//   x_in      : Q1.15 signed input sample
//   valid_out : high one cycle when output is valid
//   y_out     : Q1.15 signed squared output (always >= 0)

module squarer (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        valid_in,
    input  logic signed [15:0] x_in,
    output logic        valid_out,
    output logic signed [15:0] y_out
);

    // 32-bit intermediate for Q1.15 multiply
    logic signed [31:0] product;
    logic signed [31:0] shifted;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y_out     <= 16'sd0;
        end
        else if (valid_in) begin
            // Q1.15 multiply: 16×16 → 32-bit intermediate
            // Must use $signed to ensure signed multiplication
            product = $signed(x_in) * $signed(x_in);

            // Shift right 15 to restore Q1.15 format
            shifted = product >>> 15;

            // Saturate to 16-bit
            // In practice output is always 0 to +32767 (never negative)
            // but saturation kept for pipeline consistency
            if      (shifted > 32'sd32767)  y_out <= 16'sd32767;
            else if (shifted < -32'sd32768) y_out <= -16'sd32768;
            else                            y_out <= shifted[15:0];

            valid_out <= 1'b1;
        end
        else begin
            valid_out <= 1'b0;
        end
    end

endmodule