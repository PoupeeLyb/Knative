#include <iostream>
#include <vector>
#include <random>
#include <chrono>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <iomanip>
#include <ctime>
#include <Eigen/Dense>

using namespace std;
using namespace Eigen;

// 打印时间戳(ms)及北京时间
void print_timestamp(const string &label) {
    using namespace std::chrono;
    auto now = system_clock::now();
    auto ms = duration_cast<milliseconds>(now.time_since_epoch()).count();

    time_t t = ms / 1000;
    std::tm bt;
    t += 8*3600; // 北京时间
    gmtime_r(&t, &bt);

    int ms_part = ms % 1000;

    cout << "[" << label << "] 时间戳: " << ms
         << " ms (" << put_time(&bt, "%Y-%m-%d %H:%M:%S")
         << "." << setw(3) << setfill('0') << ms_part << " 北京时间)" << endl;
}

// 生成随机线性系统
void generate_linear_system(int m, int n, MatrixXd &A, VectorXd &b, VectorXd &x_true, double sparse_ratio = 0.0) {
    mt19937 rng(42);
    normal_distribution<double> dist(0.0, 1.0);

    x_true = VectorXd(n);
    for(int i = 0; i < n; i++) x_true(i) = dist(rng);

    A = MatrixXd(m, n);
    for(int i = 0; i < m; i++)
        for(int j = 0; j < n; j++)
            A(i,j) = dist(rng);

    if(sparse_ratio > 0.0){
        uniform_real_distribution<double> mask_dist(0.0,1.0);
        for(int i=0;i<m;i++)
            for(int j=0;j<n;j++)
                if(mask_dist(rng) < sparse_ratio) A(i,j) = 0.0;
    }

    b = A*x_true + VectorXd::Random(m)*1e-10;
}

// 求解器
VectorXd solve_dense_lu(const MatrixXd &A, const VectorXd &b) { return A.lu().solve(b); }
VectorXd solve_least_squares(const MatrixXd &A, const VectorXd &b) { return A.bdcSvd(ComputeThinU|ComputeThinV).solve(b); }
VectorXd solve_qr(const MatrixXd &A, const VectorXd &b) { return A.colPivHouseholderQr().solve(b); }
VectorXd solve_svd(const MatrixXd &A, const VectorXd &b) { return A.bdcSvd(ComputeThinU|ComputeThinV).solve(b); }

double residual_norm(const MatrixXd &A, const VectorXd &x, const VectorXd &b) { return (A*x - b).norm(); }

struct SolverResult{
    string name;
    VectorXd x;
    double time_sec;
    double residual;
    double error;
};

int main(int argc, char **argv){
    print_timestamp("程序启动");

    if(argc < 3){
        cerr << "用法: " << argv[0] << " m n [--sparse ratio]" << endl;
        return 1;
    }

    int m = stoi(argv[1]), n = stoi(argv[2]);
    double sparse_ratio = 0.0;
    for(int i=3;i<argc;i++){
        string arg = argv[i];
        if(arg=="--sparse" && i+1<argc){
            sparse_ratio = stod(argv[i+1]);
            i++;
        }
    }

    MatrixXd A; VectorXd b, x_true;
    generate_linear_system(m,n,A,b,x_true,sparse_ratio);

    cout << string(60,'=') << endl;
    cout << "线性方程组求解 Benchmark" << endl;
    cout << "矩阵大小: " << m << " x " << n << endl;
    cout << string(60,'=') << endl;

    vector<SolverResult> results;

    auto try_solver = [&](const string &name, auto solver_func){
        try{
            auto start = chrono::high_resolution_clock::now();
            VectorXd x = solver_func(A,b);
            auto end = chrono::high_resolution_clock::now();
            chrono::duration<double> elapsed = end-start;

            double res = residual_norm(A,x,b);
            double err = (x_true.size()==x.size())?(x-x_true).norm():0.0;

            cout << "\n运行 " << name << "..." << endl;
            cout << "  时间: " << elapsed.count() << " 秒" << endl;
            cout << "  残差范数: " << res << endl;
            if(x_true.size()==x.size()) cout << "  误差范数: " << err << endl;

            results.push_back({name,x,elapsed.count(),res,err});
        } catch(exception &e){
            cout << "  失败: " << e.what() << endl;
        }
    };

    if(m==n) try_solver("LU分解", solve_dense_lu);
    try_solver("QR分解", solve_qr);
    try_solver("最小二乘", solve_least_squares);
    if(min(m,n)<=1000) try_solver("SVD分解", solve_svd);

    auto best_it = min_element(results.begin(), results.end(),
        [](const SolverResult &a,const SolverResult &b){return a.time_sec < b.time_sec;});

    cout << string(60,'=') << endl;
    if(best_it != results.end()){
        cout << "最佳求解器: " << best_it->name << endl;
        cout << "求解时间: " << best_it->time_sec << " 秒" << endl;
        cout << "残差范数: " << best_it->residual << endl;
        cout << "误差范数: " << best_it->error << endl;

        cout << "\n解向量 (前10个元素):" << endl;
        for(int i=0;i<min(10,(int)best_it->x.size());i++) cout << best_it->x(i) << " ";
        if(best_it->x.size()>10) cout << "... (共 " << best_it->x.size() << " 个元素)";
        cout << endl;
    }

    print_timestamp("程序结束");

    return 0;
}

