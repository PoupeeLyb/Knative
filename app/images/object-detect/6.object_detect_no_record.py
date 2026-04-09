#!/usr/bin/env python3
"""
目标检测程序 - 使用 YOLOv8n 模型进行目标检测
基于 Rust 实现的 Python 版本
"""

import sys
import os
import time
import torch
import numpy as np
from PIL import Image
import argparse
from datetime import datetime

# YOLO 80类标签 (COCO数据集)
YOLO_CLASSES = [
    "person",
    "bicycle",
    "car",
    "motorbike",
    "aeroplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "sofa",
    "pottedplant",
    "bed",
    "diningtable",
    "toilet",
    "tvmonitor",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]

SIZE = 640


class InferenceResult:
    """检测结果类"""
    def __init__(self, x, y, width, height, class_name, probability):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.class_name = class_name
        self.probability = probability
    
    def __repr__(self):
        return (f"InferenceResult {{ x: {self.x}, y: {self.y}, "
                f"width: {self.width}, height: {self.height}, "
                f"class: \"{self.class_name}\", probability: {self.probability:.4f} }}")


def pre_process_image(image_path):
    """
    图像预处理
    - 读取图像
    - 等比例缩放到 640x640
    - 归一化到 [0, 1]
    - 转换为 CHW 格式 (Channel, Height, Width)
    
    返回: (tensor_data, resize_scale)
    """
    # 读取图像
    img = Image.open(image_path).convert('RGB')
    original_width, original_height = img.size
    
    # 计算缩放比例
    length = max(original_width, original_height)
    scale = length / SIZE
    
    # 计算新的尺寸（保持纵横比）
    if original_width > original_height:
        new_width = SIZE
        new_height = int(SIZE * original_height / original_width)
    else:
        new_height = SIZE
        new_width = int(SIZE * original_width / original_height)
    
    # 缩放图像
    resized = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
    
    # 创建 640x640 的黑色背景图像
    resized_640x640 = Image.new('RGB', (SIZE, SIZE), (0, 0, 0))
    resized_640x640.paste(resized, (0, 0))
    
    # 转换为 numpy 数组并归一化
    img_array = np.array(resized_640x640, dtype=np.float32) / 255.0
    
    # 转换为 CHW 格式
    img_tensor = np.transpose(img_array, (2, 0, 1))  # HWC -> CHW
    
    return img_tensor, scale


def calculate_iou(box1, box2):
    """
    计算两个边界框的 IoU (Intersection over Union)
    box: InferenceResult 对象
    """
    # 计算交集区域
    x1_max = max(box1.x, box2.x)
    y1_max = max(box1.y, box2.y)
    x2_min = min(box1.x + box1.width, box2.x + box2.width)
    y2_min = min(box1.y + box1.height, box2.y + box2.height)
    
    # 计算交集面积
    intersection_width = max(0, x2_min - x1_max)
    intersection_height = max(0, y2_min - y1_max)
    intersection_area = intersection_width * intersection_height
    
    # 计算并集面积
    box1_area = box1.width * box1.height
    box2_area = box2.width * box2.height
    union_area = box1_area + box2_area - intersection_area
    
    # 计算 IoU
    if union_area == 0:
        return 0.0
    return intersection_area / union_area


def non_max_suppression(results, iou_threshold=0.5):
    """
    非极大值抑制 (NMS)，去除重叠的检测框
    
    参数:
        results: 检测结果列表
        iou_threshold: IoU 阈值，超过此值的重叠框将被抑制
    
    返回: 过滤后的检测结果列表
    """
    if len(results) == 0:
        return results
    
    # 按置信度排序（从高到低）
    results_sorted = sorted(results, key=lambda x: x.probability, reverse=True)
    
    keep = []
    while len(results_sorted) > 0:
        # 保留置信度最高的检测
        best = results_sorted.pop(0)
        keep.append(best)
        
        # 过滤与当前检测重叠度过高的其他检测（仅同类别）
        results_sorted = [
            r for r in results_sorted
            if r.class_name != best.class_name or calculate_iou(best, r) < iou_threshold
        ]
    
    return keep


def post_process_results(output_tensor, conf_threshold, scale):
    """
    后处理检测结果
    - 过滤低置信度的检测
    - 转换坐标到原始图像尺寸
    - 应用 NMS 去除重复检测
    
    参数:
        output_tensor: 模型输出 [1, 84, 8400]
        conf_threshold: 置信度阈值
        scale: 图像缩放比例
    
    返回: 检测结果列表
    """
    # 输出形状: [1, 84, 8400]
    # 前4个是边界框坐标 (x_center, y_center, width, height)
    # 后80个是类别概率
    
    # 转置为 [8400, 84]
    output = output_tensor.squeeze(0).T  # [8400, 84]
    
    results = []
    
    for row in output:
        # 获取类别概率（跳过前4个边界框坐标）
        class_probs = row[4:]
        max_prob = torch.max(class_probs).item()
        
        # 过滤低置信度
        if max_prob < conf_threshold:
            continue
        
        # 获取类别索引
        class_idx = torch.argmax(class_probs).item()
        class_name = YOLO_CLASSES[class_idx]
        
        # 获取边界框坐标 (中心点格式)
        x_center = row[0].item()
        y_center = row[1].item()
        raw_w = row[2].item()
        raw_h = row[3].item()
        
        # 转换为左上角坐标
        x = int((x_center - 0.5 * raw_w) * scale)
        y = int((y_center - 0.5 * raw_h) * scale)
        w = int(raw_w * scale)
        h = int(raw_h * scale)
        
        results.append(InferenceResult(x, y, w, h, class_name, max_prob))
    
    # 应用 NMS 去除重复检测
    results = non_max_suppression(results, iou_threshold=0.5)
    
    return results


def main():
    """主函数"""
    start_timestamp_ms = int(time.time() * 1000)
    start_time_str = datetime.fromtimestamp(start_timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"[程序启动] 时间戳: {start_timestamp_ms} ms ({start_time_str})")

    # 使用 argparse 统一处理所有参数
    parser = argparse.ArgumentParser(description='目标检测程序 - YOLOv8n 目标检测')
    parser.add_argument('model_path', type=str, help='模型文件路径')
    parser.add_argument('image_path', type=str, help='图片文件路径')
    parser.add_argument('iterations', type=int, nargs='?', default=1, 
                        help='推理迭代次数 (默认: 1)')
    parser.add_argument('--image-level', type=str, help='运行的容器镜像等级')
    parser.add_argument('--h-runtime', type=str, help='高级运行时')
    parser.add_argument('--l-runtime', type=str, help='低级运行时')
    
    args = parser.parse_args()
    
    model_path = args.model_path
    image_path = args.image_path
    iterations = args.iterations
    
    print(f"model_bin_name {model_path}")
    print(f"image_name {image_path}")
    
    # 加载 TorchScript 模型
    try:
        model = torch.jit.load(model_path)
        model.eval()
        print(f"Loaded model from file: {model_path}")
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)
    
    # 预处理图像（只需要处理一次）
    try:
        img_tensor, resize_scale = pre_process_image(image_path)
        print(f"Read input tensor, size in bytes: {img_tensor.size * img_tensor.itemsize}")
    except Exception as e:
        print(f"Error processing image: {e}")
        sys.exit(1)
    
    # 转换为 PyTorch tensor
    input_tensor = torch.from_numpy(img_tensor).unsqueeze(0)  # 添加 batch 维度 [1, 3, 640, 640]
    
    print(f"\nRunning {iterations} iteration(s)...")
    print("=" * 80)
    
    # 记录总时间
    total_start_time = time.time()
    confidence_threshold = 0.5
    
    # 循环执行推理
    for iteration in range(iterations):
        iter_start_time = time.time()
        
        print(f"\n[Iteration {iteration + 1}/{iterations}]")
        print("Performing inference...")
        
        # 模型推理
        with torch.no_grad():
            output = model(input_tensor)
        
        iter_elapsed = time.time() - iter_start_time
        
        # 后处理结果
        results = post_process_results(output, confidence_threshold, resize_scale)
        
        # 显示结果（只在第一次或每10次显示详细结果）
        if iteration == 0 or (iteration + 1) % 10 == 0 or iteration == iterations - 1:
            print(f"Inference time: {iter_elapsed:.4f}s")
            print(f"\nDetected {len(results)} objects:")
            for result in results:
                print(result)
        else:
            # 只显示简要信息
            print(f"Inference time: {iter_elapsed:.4f}s - Detected {len(results)} objects")
    
    # 显示总体统计
    total_elapsed = time.time() - total_start_time
    avg_time = total_elapsed / iterations
    
    print("\n" + "=" * 80)
    print(f"Completed {iterations} iteration(s)")
    print(f"Total time: {total_elapsed:.4f}s")
    print(f"Average inference time: {avg_time:.4f}s")
    print(f"Throughput: {iterations / total_elapsed:.2f} inferences/second")
    
    # 记录程序结束时间戳（毫秒精度）
    end_timestamp_ms = int(time.time() * 1000)
    end_time_str = datetime.fromtimestamp(end_timestamp_ms / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    total_runtime_ms = end_timestamp_ms - start_timestamp_ms

    print(f"[程序结束] 时间戳: {end_timestamp_ms} ms ({end_time_str})")
    print(f"[总运行时间] {total_runtime_ms} ms ({total_runtime_ms/1000:.3f} 秒)")

if __name__ == "__main__":
    main()

