/* L00 作业：编译第一个真实的 RISC-V 程序
 *
 * 这段代码用 ITCM（0x0）里的指令运行，把结果写进 DTCM（0x10000）里的全局变量。
 * 检查器会解析符号表，直接在它应该在的地址上核对结果。
 */

volatile int answer;      /* .bss，位于 DTCM */
volatile int steps;       /* .bss，位于 DTCM */

static int add_up(int n) {
  int sum = 0;
  for (int i = 1; i <= n; i++) {
    sum += i;
  }
  return sum;
}

int main(void) {
  steps = 9;
  answer = add_up(steps);   /* 1+...+9 = 45 */
  return 0;
}

