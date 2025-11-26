#!/usr/bin/env python3
"""
Test video feed smoothness with and without buffer flushing
"""
import cv2
import time
import numpy as np

def test_buffer_mode(flush_buffer: bool, test_duration: int = 5):
    """Test frame timing with or without buffer flushing"""
    print(f"\n{'='*60}")
    print(f"Testing with flush_buffer={flush_buffer}")
    print(f"{'='*60}")

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FPS, 60)

    frame_times = []
    start_time = time.time()
    frame_count = 0

    while time.time() - start_time < test_duration:
        loop_start = time.time()

        # Read frame with or without flushing
        if flush_buffer:
            # Flush buffer method (grab 2 frames, retrieve latest)
            for _ in range(2):
                if not cap.grab():
                    break
            ret, frame = cap.retrieve()
        else:
            # Normal read
            ret, frame = cap.read()

        if ret:
            frame_count += 1
            frame_time = time.time() - loop_start
            frame_times.append(frame_time)

            # Simulate processing delay (like YOLO)
            if frame_count % 3 == 0:
                time.sleep(0.14)  # Simulate 140ms YOLO inference

    cap.release()

    # Calculate statistics
    avg_time = np.mean(frame_times) * 1000
    std_time = np.std(frame_times) * 1000
    min_time = np.min(frame_times) * 1000
    max_time = np.max(frame_times) * 1000
    fps = frame_count / test_duration

    print(f"\nResults after {test_duration}s:")
    print(f"  Total frames: {frame_count}")
    print(f"  Actual FPS: {fps:.1f}")
    print(f"  Frame time: {avg_time:.1f}ms ± {std_time:.1f}ms")
    print(f"  Min/Max: {min_time:.1f}ms / {max_time:.1f}ms")
    print(f"  Jitter (std): {std_time:.1f}ms")

    return {
        'fps': fps,
        'avg_time': avg_time,
        'jitter': std_time
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Video Feed Smoothness Test")
    print("Simulating YOLO inference delay every 3rd frame")
    print("="*60)

    # Test without flushing
    results_no_flush = test_buffer_mode(flush_buffer=False, test_duration=5)

    # Wait a bit
    time.sleep(1)

    # Test with flushing
    results_flush = test_buffer_mode(flush_buffer=True, test_duration=5)

    # Compare
    print("\n" + "="*60)
    print("COMPARISON:")
    print("="*60)
    print(f"Without flush: {results_no_flush['fps']:.1f} FPS, jitter: {results_no_flush['jitter']:.1f}ms")
    print(f"With flush:    {results_flush['fps']:.1f} FPS, jitter: {results_flush['jitter']:.1f}ms")
    print(f"\nJitter improvement: {results_no_flush['jitter'] - results_flush['jitter']:.1f}ms")
