import org.apache.commons.math3.linear.*;
import java.util.Random;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.time.Duration;

public class main {

    static class Result {
        String solver;
        boolean success;
        double timeSec;
        double residual;
        double error;
        RealVector solution;
        String errorMsg;
    }

    static final Random random = new Random(42);

    /* ================== 生成线性系统 ================== */
    static class LinearSystem {
        RealMatrix A;
        RealVector b;
        RealVector xTrue;
    }

    static LinearSystem generate(int m, int n) {
        LinearSystem sys = new LinearSystem();

        double[][] data = new double[m][n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                data[i][j] = random.nextGaussian();

        sys.A = new Array2DRowRealMatrix(data);

        double[] x = new double[n];
        for (int i = 0; i < n; i++)
            x[i] = random.nextGaussian();

        sys.xTrue = new ArrayRealVector(x);
        sys.b = sys.A.operate(sys.xTrue);

        return sys;
    }

    /* ================== 求解器 ================== */

    static Result benchmark(String name, Solver solver, RealMatrix A, RealVector b, RealVector xTrue) {
        Result r = new Result();
        r.solver = name;
        try {
            long start = System.nanoTime();
            r.solution = solver.solve(A, b);
            long end = System.nanoTime();

            r.timeSec = (end - start) / 1e9;
            r.residual = A.operate(r.solution).subtract(b).getNorm();
            r.error = (xTrue != null && xTrue.getDimension() == r.solution.getDimension())
                    ? r.solution.subtract(xTrue).getNorm()
                    : Double.NaN;

            r.success = true;
        } catch (Exception e) {
            r.success = false;
            r.errorMsg = e.getMessage();
        }
        return r;
    }

    interface Solver {
        RealVector solve(RealMatrix A, RealVector b);
    }

    /* ================== 主程序 ================== */
    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("用法: java main <m> <n>");
            System.exit(1);
        }

        int m = Integer.parseInt(args[0]);
        int n = Integer.parseInt(args[1]);

        // 时间格式化器
        DateTimeFormatter timeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss.SSS");

        // 程序开始时间
        LocalTime startTime = LocalTime.now();
        System.out.println("[程序启动] 时间: " + startTime.format(timeFormatter));
        System.out.println("矩阵规模 (m x n): " + m + " x " + n);

        LinearSystem sys = generate(m, n);
        Result best = null;

        if (m == n) {
            best = run("LU 分解",
                    (A, b) -> new LUDecomposition(A).getSolver().solve(b),
                    sys, best);
        }

        best = run("QR 分解",
                (A, b) -> new QRDecomposition(A).getSolver().solve(b),
                sys, best);

        best = run("SVD 分解",
                (A, b) -> new SingularValueDecomposition(A).getSolver().solve(b),
                sys, best);

        if (best != null && best.success) {
            System.out.println("\n最佳求解器: " + best.solver);
            System.out.printf("时间: %.6f 秒\n", best.timeSec);
            System.out.printf("残差范数: %.2e\n", best.residual);
            System.out.printf("误差范数: %.2e\n", best.error);

            System.out.println("\n解向量 (前10个元素):");
            for (int i = 0; i < Math.min(10, best.solution.getDimension()); i++)
                System.out.printf("%.6f ", best.solution.getEntry(i));
            System.out.println();
        }

        // 程序结束时间
        LocalTime endTime = LocalTime.now();
        System.out.println("[程序结束] 时间: " + endTime.format(timeFormatter));

        // 总运行时间（毫秒）
        long durationMs = Duration.between(startTime, endTime).toMillis();
        System.out.println("[总运行时间] " + durationMs + " ms");
    }

    static Result run(String name, Solver solver, LinearSystem sys, Result best) {
        System.out.println("\n运行 " + name + "...");
        Result r = benchmark(name, solver, sys.A, sys.b, sys.xTrue);

        if (r.success) {
            System.out.printf("  时间: %.6f 秒\n", r.timeSec);
            System.out.printf("  残差: %.2e\n", r.residual);
            System.out.printf("  误差: %.2e\n", r.error);

            if (best == null || r.timeSec < best.timeSec)
                best = r;
        } else {
            System.out.println("  失败: " + r.errorMsg);
        }
        return best;
    }
}

