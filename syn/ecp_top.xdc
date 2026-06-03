# ecg_top.xdc
# ===========
# Timing constraints for ECG AF Classifier
# Target: Artix-7 xc7a35tcpg236-1
# Clock: 100 MHz (10ns period)

create_clock -period 76.000 -name clk [get_ports clk]

# Input/output delay constraints (relaxed — no physical I/O in this design)
set_input_delay  -clock clk 2.0 [all_inputs]
set_output_delay -clock clk 2.0 [all_outputs]