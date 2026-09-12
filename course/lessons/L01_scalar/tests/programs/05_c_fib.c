/* L01 测试 5：用真实交叉编译器编译的 C 程序
 *
 * 这是和上游仓库最接近的一步：同样的 riscv64-unknown-elf-gcc、
 * 同样的地址映射（ITCM 0 / DTCM 0x10000），只不过启动代码是我们精简过的。
 */

volatile int results[16];

int fib(int n) {
  int a = 0, b = 1;
  for (int i = 0; i < n; i++) {
    int next = a + b;
    a = b;
    b = next;
    results[i] = a;
  }
  return a;
}

int main(void) {
  int last = fib(10);
  results[15] = last;
  return last == 55 ? 0 : 1;
}
