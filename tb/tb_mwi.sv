`timescale 1ns/1ps

module tb_mwi;

    logic        clk;
    logic        rst_n;
    logic        valid_in;
    logic signed [15:0] x_in;
    logic        valid_out;
    logic signed [15:0] y_out;

    mwi dut (
        .clk       (clk),
        .rst_n     (rst_n),
        .valid_in  (valid_in),
        .x_in      (x_in),
        .valid_out (valid_out),
        .y_out     (y_out)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    localparam N_VECTORS = 1024;
    localparam PIPELINE  = 30;     // window size — skip first 30 outputs
    localparam TOLERANCE = 2;

    logic [15:0] in_vec  [0:N_VECTORS-1];
    logic [15:0] exp_vec [0:N_VECTORS-1];

    integer i;
    integer pass_count;
    integer fail_count;
    integer diff;
    integer out_idx;

    initial begin
        $readmemh("D:/Project_3/vectors/mwi_input_hex.txt",  in_vec);
        $readmemh("D:/Project_3/vectors/mwi_output_hex.txt", exp_vec);

        rst_n      = 0;
        valid_in   = 0;
        x_in       = 0;
        pass_count = 0;
        fail_count = 0;
        out_idx    = 0;

        repeat(5) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        $display("==============================================");
        $display("  MWI TESTBENCH");
        $display("==============================================");

        for (i = 0; i < N_VECTORS; i++) begin
            @(posedge clk);
            valid_in = 1;
            x_in     = $signed(in_vec[i]);
        end

        valid_in = 0;
        repeat(PIPELINE + 5) @(posedge clk);

        $display("  Pass : %0d", pass_count);
        $display("  Fail : %0d", fail_count);
        $display("  Total: %0d", pass_count + fail_count);
        if (fail_count == 0)
            $display("  RESULT: ALL PASS");
        else
            $display("  RESULT: FAILURES DETECTED");
        $display("==============================================");
        $finish;
    end

    always @(posedge clk) begin
        if (valid_out) begin
            if (out_idx >= PIPELINE) begin
                diff = $signed(y_out) - $signed(exp_vec[out_idx - 1]);
                if (diff < 0) diff = -diff;

                if (diff <= TOLERANCE)
                    pass_count <= pass_count + 1;
                else begin
                    fail_count <= fail_count + 1;
                    if (fail_count < 5)
                        $display("  FAIL idx=%0d got=%0d exp=%0d diff=%0d",
                                 out_idx, $signed(y_out),
                                 $signed(exp_vec[out_idx - 1]), diff);
                end
            end
            out_idx <= out_idx + 1;
        end
    end

endmodule