#!/usr/bin/env python3
"""
线性方程组求解 Benchmark 程序

输入: m, n - 矩阵维度 (m x n)
输出: 方程组的解

该程序生成随机的线性方程组 Ax = b，并使用不同的求解方法进行求解。
支持方形矩阵的精确求解和超定/欠定系统的最小二乘求解。
"""

import numpy as np
import time
import sys
import argparse
from scipy.linalg import solve, lstsq
from scipy.sparse.linalg import spsolve
from scipy.sparse import csc_matrix
import warnings
from datetime import datetime
import os

def generate_linear_system(m, n, condition_number=None, sparse_ratio=0.0):
    """
    生成线性方程组 Ax = b
    
    Args:
        m (int): 矩阵行数
        n (int): 矩阵列数
        condition_number (float): 条件数，用于控制矩阵的数值稳定性
        sparse_ratio (float): 稀疏比例 (0-1)，0表示稠密矩阵
    
    Returns:
        A (ndarray): 系数矩阵 (m x n)
        b (ndarray): 右侧向量 (m,)
        x_true (ndarray): 真实解 (n,) - 仅当 m >= n 时有意义
    """
    np.random.seed(42)  # 保证结果可重现
    
    # 生成真实解
    x_true = np.random.randn(n)
    
    if condition_number is None:
        # 生成随机矩阵
        A = np.random.randn(m, n)
    else:
        # 生成具有指定条件数的矩阵
        if m == n:
            U, _, Vt = np.linalg.svd(np.random.randn(n, n))
            s = np.logspace(0, -np.log10(condition_number), n)
            A = U @ np.diag(s) @ Vt
        else:
            A = np.random.randn(m, n)
    
    # 添加稀疏性
    if sparse_ratio > 0:
        mask = np.random.random((m, n)) > sparse_ratio
        A = A * mask
    
    # 计算右侧向量
    b = A @ x_true
    
    # 添加少量噪声使问题更真实
    b += 1e-10 * np.random.randn(m)
    
    return A, b, x_true

def solve_dense_lu(A, b):
    """使用 LU 分解求解 (适用于方形矩阵)"""
    if A.shape[0] != A.shape[1]:
        raise ValueError("LU 分解需要方形矩阵")
    return solve(A, b)

def solve_least_squares(A, b):
    """使用最小二乘法求解 (适用于超定系统)"""
    x, residuals, rank, s = lstsq(A, b)
    return x

def solve_qr_decomposition(A, b):
    """使用 QR 分解求解"""
    Q, R = np.linalg.qr(A)
    if A.shape[0] >= A.shape[1]:
        # 超定或方形系统
        y = Q.T @ b
        x = np.linalg.solve(R[:A.shape[1], :], y[:A.shape[1]])
    else:
        # 欠定系统 - 使用最小范数解
        x = np.linalg.pinv(A) @ b
    return x

def solve_svd(A, b):
    """使用 SVD 分解求解 (最稳健但最慢)"""
    return np.linalg.pinv(A) @ b

def solve_sparse(A, b):
    """使用稀疏矩阵求解器"""
    if A.shape[0] != A.shape[1]:
        raise ValueError("稀疏求解器需要方形矩阵")
    A_sparse = csc_matrix(A)
    return spsolve(A_sparse, b)

def benchmark_solver(solver_func, A, b, solver_name, x_true=None):
    """
    对求解器进行 benchmark
    
    Args:
        solver_func: 求解函数
        A: 系数矩阵
        b: 右侧向量
        solver_name: 求解器名称
        x_true: 真实解（可选）
    
    Returns:
        dict: benchmark 结果
    """
    try:
        start_time = time.perf_counter()
        x = solver_func(A, b)
        end_time = time.perf_counter()
        
        solve_time = end_time - start_time
        
        # 计算残差
        residual_norm = np.linalg.norm(A @ x - b)
        
        # 如果有真实解，计算误差
        error_norm = None
        if x_true is not None and len(x) == len(x_true):
            error_norm = np.linalg.norm(x - x_true)
        
        return {
            'solver': solver_name,
            'success': True,
            'time': solve_time,
            'residual_norm': residual_norm,
            'error_norm': error_norm,
            'solution': x
        }
    
    except Exception as e:
        return {
            'solver': solver_name,
            'success': False,
            'error': str(e),
            'time': None,
            'residual_norm': None,
            'error_norm': None,
            'solution': None
        }

def run_benchmark(m, n, verbose=True, condition_number=None, sparse_ratio=0.0):
    """
    运行线性方程组求解 benchmark
    
    Args:
        m (int): 矩阵行数
        n (int): 矩阵列数
        verbose (bool): 是否输出详细信息
        condition_number (float): 矩阵条件数
        sparse_ratio (float): 稀疏比例
    
    Returns:
        dict: benchmark 结果
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"线性方程组求解 Benchmark")
        print(f"矩阵大小: {m} x {n}")
        if condition_number:
            print(f"条件数: {condition_number:.2e}")
        if sparse_ratio > 0:
            print(f"稀疏比例: {sparse_ratio:.2f}")
        print(f"{'='*60}")
    
    # 生成线性系统
    A, b, x_true = generate_linear_system(m, n, condition_number, sparse_ratio)
    
    # if verbose:
    #     print(f"矩阵条件数: {np.linalg.cond(A):.2e}")
    #     print(f"矩阵秩: {np.linalg.matrix_rank(A)}")
    
    # 选择适用的求解器
    solvers = []
    
    if m == n:
        # 方形矩阵
        solvers.extend([
            (solve_dense_lu, "LU分解"),
            (solve_qr_decomposition, "QR分解"),
            (solve_least_squares, "最小二乘"),
        ])
        
        # 如果矩阵不是太大，添加稀疏求解器
        if m <= 5000 and sparse_ratio > 0.1:
            solvers.append((solve_sparse, "稀疏求解"))
    else:
        # 非方形矩阵
        solvers.extend([
            (solve_least_squares, "最小二乘"),
            (solve_qr_decomposition, "QR分解"),
        ])
    
    # 对于小矩阵，添加 SVD 求解器
    if min(m, n) <= 1000:
        solvers.append((solve_svd, "SVD分解"))
    
    # 运行 benchmark
    results = []
    for solver_func, solver_name in solvers:
        if verbose:
            print(f"\n运行 {solver_name}...")
        
        result = benchmark_solver(solver_func, A, b, solver_name, x_true)
        results.append(result)
        
        if verbose and result['success']:
            print(f"  时间: {result['time']:.6f} 秒")
            print(f"  残差范数: {result['residual_norm']:.2e}")
            if result['error_norm'] is not None:
                print(f"  误差范数: {result['error_norm']:.2e}")
        elif verbose:
            print(f"  失败: {result['error']}")
    
    # 找到最佳求解器（基于时间）
    successful_results = [r for r in results if r['success']]
    if successful_results:
        best_solver = min(successful_results, key=lambda x: x['time'])
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"最佳求解器: {best_solver['solver']}")
            print(f"求解时间: {best_solver['time']:.6f} 秒")
            print(f"残差范数: {best_solver['residual_norm']:.2e}")
            if best_solver['error_norm'] is not None:
                print(f"误差范数: {best_solver['error_norm']:.2e}")
        
        return {
            'matrix_size': (m, n),
            'condition_number': np.linalg.cond(A),
            'results': results,
            'best_solver': best_solver,
            'solution': best_solver['solution']
        }
    else:
        if verbose:
            print("\n所有求解器都失败了!")
        return {
            'matrix_size': (m, n),
            'condition_number': np.linalg.cond(A),
            'results': results,
            'best_solver': None,
            'solution': None
        }

def main():
    """主函数"""
    start_timestamp_ms = int(time.time() * 1000)
    start_time_str = datetime.fromtimestamp(start_timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[程序启动] 时间戳: {start_timestamp_ms} ms ({start_time_str})")
    
    parser = argparse.ArgumentParser(description='线性方程组求解 Benchmark')
    parser.add_argument('m', type=int, help='矩阵行数')
    parser.add_argument('n', type=int, help='矩阵列数')
    parser.add_argument('--condition', type=float, help='矩阵条件数')
    parser.add_argument('--sparse', type=float, default=0.0, 
                       help='稀疏比例 (0-1)')
    parser.add_argument('--quiet', action='store_true', 
                       help='安静模式，只输出结果')
    parser.add_argument('--image-level', type=str, help='运行的容器镜像等级')
    parser.add_argument('--h-runtime', type=str, help='高级运行时')
    parser.add_argument('--l-runtime', type=str, help='低级运行时')
    
    args = parser.parse_args()
    
    if args.m <= 0 or args.n <= 0:
        print("错误: 矩阵维度必须为正数")
        sys.exit(1)
    
    if args.sparse < 0 or args.sparse > 1:
        print("错误: 稀疏比例必须在 0-1 之间")
        sys.exit(1)
    
    # 忽略一些数值警告
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    
    # 运行 benchmark
    result = run_benchmark(
        args.m, args.n, 
        verbose=not args.quiet,
        condition_number=args.condition,
        sparse_ratio=args.sparse
    )
    
    # 输出最终结果
    if result['solution'] is not None:
        print(f"\n解向量 (前10个元素):")
        solution = result['solution']
        print(solution[:min(10, len(solution))])
        if len(solution) > 10:
            print(f"... (共 {len(solution)} 个元素)")
    else:
        print("\n未找到有效解")
    
    end_timestamp_ms = int(time.time() * 1000)
    end_time_str = datetime.fromtimestamp(end_timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    total_runtime_ms = end_timestamp_ms - start_timestamp_ms

    print(f"[程序结束] 时间戳: {end_timestamp_ms} ms ({end_time_str})")
    print(f"[总运行时间] {total_runtime_ms} ms ({total_runtime_ms/1000:.3f} 秒)")
    
    return 0 if result['best_solver'] is not None else 1

if __name__ == "__main__":
    sys.exit(main())

