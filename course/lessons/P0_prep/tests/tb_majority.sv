// P0 测试平台：多数表决器（向量驱动）
// 输入文件每行 "a b c"，输出文件每行 "y"

`timescale 1ns/1ps

module tb_majority;
  logic a, b, c, y;
  string vectors_path, results_path;
  int in_fd, out_fd, code, n;

  majority dut (.a(a), .b(b), .c(c), .y(y));

  initial begin
    vectors_path = "";
    results_path = "majority_results.txt";
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
      code = $fscanf(in_fd, "%b %b %b\n", a, b, c);
      if (code == 3) begin
        #1;
        $fdisplay(out_fd, "%b", y);
        n++;
      end
    end
    $fclose(in_fd);
    $fclose(out_fd);
    $display("OK vectors=%0d", n);
    $finish;
  end
endmodule

