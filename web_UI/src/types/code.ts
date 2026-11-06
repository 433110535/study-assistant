export type CodeSandboxStatus =
  | 'passed'
  | 'failed'
  | 'timeout'
  | 'memory'
  | 'memory_limit'
  | 'rejected'
  | 'security_violation'
  | 'error';

export interface CodeRunResult {
  status: CodeSandboxStatus;
  stdout: string;
  stderr: string;
  exit_code: number;
  duration_ms: number;
  timed_out: boolean;
  thread_id: string;
}

export interface CodeAttempt {
  id: string;
  user_id: string;
  thread_id: string;
  seq: number;
  code: string;
  tests?: string;
  status: string;
  exception_type?: string;
  exception_message?: string;
  line?: number;
  stdout_preview?: string;
  created_at: string;
}

export interface CodeTemplate {
  id: string;
  title: string;
  category: string;
  code: string;
  tests: string;
  description: string;
}

export const CODE_TEMPLATES: CodeTemplate[] = [
  {
    id: 'binary-search',
    title: '二分查找 (Binary Search)',
    category: '算法基础',
    description: '标准有序数组双指针折半查找算法，包含多组断言测试。',
    code: `def binary_search(nums, target):
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# 本地调试调用
result = binary_search([1, 3, 5, 7, 9, 11], 7)
print(f"Index of 7 is: {result}")
`,
    tests: `assert binary_search([1, 2, 3, 4, 5], 3) == 2, "Test 1 Failed"
assert binary_search([1, 2, 3, 4, 5], 6) == -1, "Test 2 Failed"
assert binary_search([], 1) == -1, "Test 3 Failed"
print("[ASSERTION_SUITE]: All 3 test cases passed!")
`,
  },
  {
    id: 'assertion-failure',
    title: '断言失败示例 (Assertion Error)',
    category: '调试教学',
    description: '函数实现与断言预期不匹配，测试沙箱异常捕获与 Traceback 报告。',
    code: `def calculate_sum(n):
    # 逻辑失误：误用乘法计算累加
    total = 1
    for i in range(1, n + 1):
        total = total * i
    return total

print("Sum of 1..5:", calculate_sum(5))
`,
    tests: `assert calculate_sum(5) == 15, f"Expected 15, but got {calculate_sum(5)}"
`,
  },
  {
    id: 'memory-limit',
    title: '64MB 内存超限拦截 (Memory Limit MLE)',
    category: '沙箱防御',
    description: '尝试分配超过 64MB 内存，验证 Windows Job Object 内存硬上限拦截。',
    code: `print("[TEST]: Attempting to allocate 128MB bytearray in sandbox...")
# 申请 128MB 堆内存，预期被 Job Object 64MB 提交上限拦截
blob = bytearray(128 * 1024 * 1024)
print("Allocation done, length:", len(blob))
`,
    tests: ``,
  },
  {
    id: 'infinite-loop',
    title: '死循环超时强杀 (Timeout TLE)',
    category: '沙箱防御',
    description: '死循环运行，验证沙箱 2.0 秒超时后 taskkill 级联进程树强杀。',
    code: `import time

print("[TEST]: Entering infinite loop...")
count = 0
while True:
    count += 1
    # 模拟耗时死循环
    if count % 1000000 == 0:
        pass
`,
    tests: ``,
  },
  {
    id: 'security-violation',
    title: '越权导入安全拦截 (Security Violation)',
    category: '沙箱防御',
    description: '尝试导入 os 模块探测宿主环境，验证 AST 静态防护。',
    code: `# 尝试越权访问宿主文件系统
import os
print("Current dir files:", os.listdir("."))
`,
    tests: ``,
  },
];

