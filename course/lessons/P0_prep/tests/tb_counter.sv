// P0 测试平台：计数器（观察固定时序下的输出序列）
//
// 序列：复位后记录 1 次 → 使能 10 个周期每次记录 → 关闭使能再记录 4 次

`timescale 1ns/1ps

module tb_counter;
  logic clk = 0;
  logic rst = 1;
  logic en = 0;
  logic [7:0] q;
  string results_path;
  int out_fd;

  counter dut (.clk(clk), .rst(rst), .en(en), .q(q));

  always #5 clk = ~clk;

  initial begin
    results_path = "counter_results.txt";
    void'($value$plusargs("RESULTS=%s", results_path));
    out_fd = $fopen(results_path, "w");

    rst = 1;
    repeat (4) @(posedge clk);
    @(negedge clk);
    rst = 0;

    @(negedge clk);
    $fdisplay(out_fd, "%02x", q);        // 复位后：0

    en = 1;
    for (int i = 0; i < 10; i++) begin
      @(posedge clk);
      @(negedge clk);
      $fdisplay(out_fd, "%02x", q);      // 每个使能周期加 1
    end

    en = 0;
    for (int i = 0; i < 4; i++) begin
      @(posedge clk);
      @(negedge clk);
      $fdisplay(out_fd, "%02x", q);      // 保持
    end

    $fclose(out_fd);
    $display("OK");
    $finish;
  end
endmodule
