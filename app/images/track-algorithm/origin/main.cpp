#include <opencv2/opencv.hpp>
#include <opencv2/videoio.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/video/tracking.hpp>
#include <iostream>
#include <vector>
#include <string>
#include <sys/time.h> // 新增，用于时间统计

// Helper function: 打印带毫秒的时间
void print_timestamp_ms(const std::string &prefix, const struct timeval &tv) {
    struct tm tm_info;
    char time_str[64];
    localtime_r(&tv.tv_sec, &tm_info);
    strftime(time_str, sizeof(time_str), "%Y-%m-%d %H:%M:%S", &tm_info);
    std::cout << prefix << " " << time_str << "." << tv.tv_usec / 1000 << std::endl;
}

int main(int argc, char **argv) {
    // ================== 时间统计：开始 ==================
    struct timeval start_tv, end_tv;
    gettimeofday(&start_tv, NULL);
    print_timestamp_ms("[MAIN][INFO] Program start time:", start_tv);
    // =====================================================

    // --- 原有视频处理逻辑不变 ---
    std::string video_path;
    if (argc > 1) {
        video_path = argv[1];
    } else {
        video_path = "video.mp4";
        std::cout << "Usage: ./ovx1_app_cn <video_file_path_or_frame_sequence_pattern>" << std::endl;
        std::cout << "No path provided, attempting to use default: " << video_path << std::endl;
    }

    cv::VideoCapture cap;
    cap.open(video_path);
    if (!cap.isOpened()) {
        cap.open(video_path, cv::CAP_IMAGES);
    }
    if (!cap.isOpened()) {
        std::cerr << "Error: Could not open video or image sequence from path: " << video_path << std::endl;
        return -1;
    }

    cv::Mat frame_4k, frame_hd_rgb, prev_gray, current_gray;
    std::vector<cv::Point2f> p0, p1;
    int maxCorners = 200;
    double qualityLevel = 0.01;
    double minDistance = 10;
    int blockSize_harris = 3;
    bool useHarrisDetector = false;
    double k_harris = 0.04;
    cv::Size winSize(21, 21);
    int maxLevel = 3;
    cv::TermCriteria criteria(cv::TermCriteria::COUNT + cv::TermCriteria::EPS, 30, 0.01);
    bool first_frame_processed = false;
    int frame_count = 0;
    const int MAX_FRAMES_TO_PROCESS = 180;

    while (frame_count < MAX_FRAMES_TO_PROCESS) {
        cap >> frame_4k;
        if (frame_4k.empty()) break;
        frame_count++;

        cv::resize(frame_4k, frame_hd_rgb, cv::Size(1280, 720));
        cv::cvtColor(frame_hd_rgb, current_gray, cv::COLOR_BGR2GRAY);

        if (!first_frame_processed) {
            cv::goodFeaturesToTrack(current_gray, p0, maxCorners, qualityLevel, minDistance, cv::Mat(),
                                    blockSize_harris, useHarrisDetector, k_harris);
            prev_gray = current_gray.clone();
            first_frame_processed = true;
        } else if (!p0.empty()) {
            std::vector<uchar> status;
            std::vector<float> err;
            cv::calcOpticalFlowPyrLK(prev_gray, current_gray, p0, p1, status, err, winSize, maxLevel, criteria);
            std::vector<cv::Point2f> good_new_points;
            for (size_t i = 0; i < p0.size(); i++) {
                if (status[i]) good_new_points.push_back(p1[i]);
            }
            p0 = good_new_points;
            prev_gray = current_gray.clone();
            if (p0.size() < static_cast<size_t>(maxCorners / 4)) {
                cv::goodFeaturesToTrack(current_gray, p0, maxCorners, qualityLevel, minDistance, cv::Mat(),
                                        blockSize_harris, useHarrisDetector, k_harris);
            }
        } else {
            cv::goodFeaturesToTrack(current_gray, p0, maxCorners, qualityLevel, minDistance, cv::Mat(),
                                    blockSize_harris, useHarrisDetector, k_harris);
            prev_gray = current_gray.clone();
        }
    }

    cap.release();

    // ================== 时间统计：结束 ==================
    gettimeofday(&end_tv, NULL);
    print_timestamp_ms("[MAIN][INFO] Program end time:", end_tv);

    long elapsed_ms = (end_tv.tv_sec - start_tv.tv_sec) * 1000 + (end_tv.tv_usec - start_tv.tv_usec) / 1000;
    std::cout << "[MAIN][INFO] Total execution time: " << elapsed_ms << " ms (" << elapsed_ms / 1000.0 << " s)" << std::endl;
    // =====================================================
    
    return 0;
}

