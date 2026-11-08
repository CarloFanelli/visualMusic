"""Reports whether the training environment is ready."""
import sys

SETUP_HINT = "Environment is not installed. Run: scripts/setup.sh"


def describe(version, gpu_available):
    lines = [f"YOLO (ultralytics) version: {version}"]
    if gpu_available:
        lines.append("Apple GPU acceleration: available")
    else:
        lines.append("Apple GPU acceleration: not available")
        lines.append("WARNING: running CPU-only, so training will be slower.")
    return lines


def main():
    try:
        import torch
        import ultralytics
    except ImportError:
        print(SETUP_HINT)
        return 1
    for line in describe(ultralytics.__version__, torch.backends.mps.is_available()):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
