// P0 测试平台：4 选 1 多路选择器
// 用四个固定数据扫描 sel=0..3，输出四行结果

`timescale 1ns/1ps

module tb_mux4;
  logic [31:0] d0, d1, d2, d3;
  logic [1:0]  sel;
  logic [31:0] y;
  string results_path;
  int out_fd;

  mux4 dut (.d0(d0), .d1(d1), .d2(d2), .d3(d3), .sel(sel), .y(y));

  initial begin
    results_path = "mux4_results.txt";
    void'($value$plusargs("RESULTS=%s", results_path));
    out_fd = $fopen(results_path, "w");

    d0 = 32'h0000_0011;
    d1 = 32'h0000_0022;
    d2 = 32'h0000_0044;
    d3 = 32'h0000_0088;

    for (int s = 0; s < 4; s++) begin
      sel = s[1:0];
      #1;
      $fdisplay(out_fd, "%08x", y);
    end
    $fclose(out_fd);
    $display("OK");
    $finish;
  end
endmodule

