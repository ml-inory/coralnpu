// L00 测试平台：向量驱动的 ALU 测试
//
// 输入文件每行三个十六进制数：a b op
// 输出文件每行两个十六进制数：y zero
//
// 运行：vvp sim.vvp +VECTORS=in.txt +RESULTS=out.txt

`timescale 1ns/1ps

module tb_alu32;
  logic [31:0] a, b;
  logic [3:0]  op;
  logic [31:0] y;
  logic        zero;

  string vectors_path;
  string results_path;
  int in_fd, out_fd, code;
  int n;

  alu32 dut (.a(a), .b(b), .op(op), .y(y), .zero(zero));

  initial begin
    vectors_path = "";
    results_path = "results.txt";
    void'($value$plusargs("VECTORS=%s", vectors_path));
    void'($value$plusargs("RESULTS=%s", results_path));
    if (vectors_path == "") begin
      $display("需要 +VECTORS=<文件>");
      $finish;
    end
    in_fd = $fopen(vectors_path, "r");
    out_fd = $fopen(results_path, "w");
    if (in_fd == 0 || out_fd == 0) begin
      $display("打不开向量文件");
      $finish;
    end

    n = 0;
    while (!$feof(in_fd)) begin
      code = $fscanf(in_fd, "%h %h %h\n", a, b, op);
      if (code == 3) begin
        #1;
        $fdisplay(out_fd, "%08x %01x", y, zero);
        n++;
      end
    end
    $fclose(in_fd);
    $fclose(out_fd);
    $display("OK vectors=%0d", n);
    $finish;
  end
endmodule
