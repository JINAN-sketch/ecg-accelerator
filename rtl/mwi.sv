`timescale 1ns/1ps

module mwi (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        valid_in,
    input  logic signed [15:0] x_in,
    output logic        valid_out,
    output logic signed [15:0] y_out
);

    localparam WINDOW = 30;

    logic signed [15:0] sr [0:WINDOW-1];
    logic signed [31:0] acc;
    logic signed [47:0] product;
    logic signed [47:0] shifted;
    integer k;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            for (k = 0; k < WINDOW; k++)
                sr[k] <= 16'sd0;
            acc       <= 32'sd0;
            valid_out <= 1'b0;
            y_out     <= 16'sd0;
        end
        else if (valid_in) begin
            // Shift register
            sr[0] <= x_in;
            for (k = 1; k < WINDOW; k++)
                sr[k] <= sr[k-1];

            // Running accumulator — add new, subtract oldest
            // Uses OLD sr[WINDOW-1] (non-blocking, not yet shifted)
            acc <= acc + $signed(x_in) - $signed(sr[WINDOW-1]);

            // Divide by 30 using OLD acc (non-blocking not yet updated)
            product = $signed(acc) * 48'sd1092;
            shifted = product >>> 15;

            // Saturate to 16-bit
            if      (shifted > 48'sd32767)  y_out <= 16'sd32767;
            else if (shifted < -48'sd32768) y_out <= -16'sd32768;
            else                            y_out <= shifted[15:0];

            valid_out <= 1'b1;
        end
        else begin
            valid_out <= 1'b0;
        end
    end

endmodule