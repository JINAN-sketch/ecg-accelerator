`timescale 1ns/1ps

module tb_mad_classifier;

    logic        clk;
    logic        rst_n;
    logic        rr_valid;
    logic [15:0] rr_interval;
    logic [1:0]  classification;
    logic [15:0] nv_q15;

    mad_classifier dut (
        .clk            (clk),
        .rst_n          (rst_n),
        .rr_valid       (rr_valid),
        .rr_interval    (rr_interval),
        .classification (classification),
        .nv_q15         (nv_q15)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    localparam N_WINDOWS = 400;
    localparam TOLERANCE = 200;

    integer fd_in, fd_out;
    integer scan_ret;
    integer rr0,rr1,rr2,rr3,rr4,rr5,rr6,rr7;
    integer lbl, nv_exp;
    integer i, j;
    integer label_pass, label_fail;
    integer nv_pass, nv_fail, nv_diff;

    logic [15:0] win_rr  [0:7];
    logic [1:0]  exp_lbl [0:N_WINDOWS-1];
    logic [15:0] exp_nv  [0:N_WINDOWS-1];
    logic [15:0] all_rr  [0:N_WINDOWS-1][0:7];

    initial begin
        fd_in  = $fopen("D:/Project_3/vectors/classifier_input.txt",  "r");
        fd_out = $fopen("D:/Project_3/vectors/classifier_output.txt", "r");

        if (fd_in  == 0) $fatal(1, "Cannot open classifier_input.txt");
        if (fd_out == 0) $fatal(1, "Cannot open classifier_output.txt");

        for (i = 0; i < N_WINDOWS; i++) begin
            scan_ret = $fscanf(fd_in, "%d %d %d %d %d %d %d %d\n",
                               rr0,rr1,rr2,rr3,rr4,rr5,rr6,rr7);
            scan_ret = $fscanf(fd_out, "%d %d\n", lbl, nv_exp);
            all_rr[i][0]=rr0; all_rr[i][1]=rr1; all_rr[i][2]=rr2; all_rr[i][3]=rr3;
            all_rr[i][4]=rr4; all_rr[i][5]=rr5; all_rr[i][6]=rr6; all_rr[i][7]=rr7;
            exp_lbl[i] = lbl;
            exp_nv[i]  = nv_exp;
        end

        $fclose(fd_in);
        $fclose(fd_out);

        rr_valid    = 0;
        rr_interval = 0;
        label_pass  = 0;
        label_fail  = 0;
        nv_pass     = 0;
        nv_fail     = 0;

        $display("==============================================");
        $display("  MAD CLASSIFIER TESTBENCH");
        $display("==============================================");

        for (i = 0; i < N_WINDOWS; i++) begin
            // Reset classifier for each independent window
            rst_n = 0;
            repeat(3) @(posedge clk);
            rst_n = 1;
            @(posedge clk);

            // Send all 8 RR values
            for (j = 0; j < 8; j++) begin
                @(posedge clk);
                rr_valid    = 1;
                rr_interval = all_rr[i][j];
            end
            @(posedge clk);
            rr_valid = 0;

            // Wait 2 cycles for output to settle
            repeat(2) @(posedge clk);

            // Check label
            if (classification == exp_lbl[i])
                label_pass = label_pass + 1;
            else begin
                label_fail = label_fail + 1;
                if (label_fail <= 5)
                    $display("  LABEL FAIL win=%0d got=%0b exp=%0b nv=%0d exp=%0d",
                             i, classification, exp_lbl[i], nv_q15, exp_nv[i]);
            end

            // Check NV
            nv_diff = nv_q15 - exp_nv[i];
            if (nv_diff < 0) nv_diff = -nv_diff;
            if (nv_diff <= TOLERANCE)
                nv_pass = nv_pass + 1;
            else begin
                nv_fail = nv_fail + 1;
                if (nv_fail <= 5)
                    $display("  NV FAIL win=%0d got=%0d exp=%0d diff=%0d",
                             i, nv_q15, exp_nv[i], nv_diff);
            end
        end

        $display("  Label pass : %0d / %0d", label_pass, N_WINDOWS);
        $display("  Label fail : %0d / %0d", label_fail, N_WINDOWS);
        $display("  NV pass    : %0d / %0d", nv_pass,    N_WINDOWS);
        $display("  NV fail    : %0d / %0d", nv_fail,    N_WINDOWS);
        if (label_fail == 0 && nv_fail == 0)
            $display("  RESULT: ALL PASS");
        else if (label_fail <= 15 && nv_fail <= 50)
            $display("  RESULT: ACCEPTABLE");
        else
            $display("  RESULT: FAILURES DETECTED");
        $display("==============================================");
        $finish;
    end

endmodule