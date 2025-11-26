# Documentation Index

## Quick Links

### Getting Started
- **[Main README](../README.md)** - Start here! Complete overview and quick start
- **[Windows Setup](WINDOWS_SETUP.md)** - Detailed Windows installation guide
- **[Cross-Platform Guide](CROSS_PLATFORM.md)** - Linux, Jetson, macOS support

### Installation & Configuration
- **[install/install_pyspin.md](install/install_pyspin.md)** - FLIR Firefly / PySpin installation
- **[install/setup_python310_env.md](install/setup_python310_env.md)** - Python 3.10 virtual environment setup
- **[install/SPINNAKER_SDK_DIAGNOSIS.md](install/SPINNAKER_SDK_DIAGNOSIS.md)** - Troubleshooting Spinnaker SDK

### Platform-Specific
- **[JETSON_GPU_SETUP.md](JETSON_GPU_SETUP.md)** - Jetson Orin/Xavier/Nano GPU optimization
- **[JETSON_ORIN_NANO_PERFORMANCE.md](JETSON_ORIN_NANO_PERFORMANCE.md)** - Performance benchmarks

### Advanced Topics
- **[CUSTOM_MODELS.md](CUSTOM_MODELS.md)** - Train custom thermal detection models
- **[DEBUGGING_GUIDELINES.md](DEBUGGING_GUIDELINES.md)** - Debug and troubleshooting
- **[LESSONS_LEARNED_ADAS_ALERTS.md](LESSONS_LEARNED_ADAS_ALERTS.md)** - ADAS development insights

### Verification
- **[CROSS_PLATFORM_VERIFICATION.md](CROSS_PLATFORM_VERIFICATION.md)** - Test checklist for all platforms

---

## Documentation Structure

```
docs/
├── README.md (this file)                       # Documentation index
│
├── Installation & Setup
│   ├── WINDOWS_SETUP.md                        # Detailed Windows guide
│   ├── CROSS_PLATFORM.md                       # Multi-platform support
│   ├── CROSS_PLATFORM_VERIFICATION.md          # Testing checklist
│   └── install/
│       ├── install_pyspin.md                   # PySpin/FLIR Firefly setup
│       ├── setup_python310_env.md              # Python 3.10 venv guide
│       └── SPINNAKER_SDK_DIAGNOSIS.md          # SDK troubleshooting
│
├── Platform-Specific
│   ├── JETSON_GPU_SETUP.md                     # Jetson optimization
│   └── JETSON_ORIN_NANO_PERFORMANCE.md         # Performance benchmarks
│
├── Advanced Topics
│   ├── CUSTOM_MODELS.md                        # Model training guide
│   ├── DEBUGGING_GUIDELINES.md                 # Debugging tips
│   └── LESSONS_LEARNED_ADAS_ALERTS.md          # ADAS development notes
│
└── archive/                                    # Old planning/development docs
    ├── GUI_CLEANUP_PLAN.md
    ├── GUI_EVALUATION_AND_LIDAR_PLAN.md
    ├── GUI_IMPROVEMENT_OPTIONS.md
    ├── QT_GUI_ARCHITECTURE.md
    ├── QT_GUI_REFACTORING_NEEDED.md
    ├── phase3_refactor.md
    ├── JITTER_DEBUG_ANALYSIS.md
    ├── ROOT_CAUSE_ANALYSIS.md
    ├── test_smoothness.py
    └── test_flir_detection.py
```

---

## Quick Setup Paths

### First-Time Windows User
1. Read: [Main README](../README.md) - Overview
2. Follow: [Windows Setup](WINDOWS_SETUP.md) - Step-by-step
3. If using FLIR Firefly: [install/install_pyspin.md](install/install_pyspin.md)

### First-Time Jetson User
1. Read: [Main README](../README.md) - Overview
2. Follow: [Cross-Platform](CROSS_PLATFORM.md) - Jetson section
3. Optimize: [Jetson GPU Setup](JETSON_GPU_SETUP.md)

### Troubleshooting
1. Camera issues: [install/SPINNAKER_SDK_DIAGNOSIS.md](install/SPINNAKER_SDK_DIAGNOSIS.md)
2. Performance issues: [DEBUGGING_GUIDELINES.md](DEBUGGING_GUIDELINES.md)
3. Platform compatibility: [CROSS_PLATFORM_VERIFICATION.md](CROSS_PLATFORM_VERIFICATION.md)

---

## Need Help?

- Check the [Main README](../README.md) for common issues
- Run diagnostic scripts:
  - `python diagnose_spinnaker.py` - SDK issues
  - `python verify_pyspin.py` - PySpin verification
  - `python camera_factory.py` - Camera detection
- See [DEBUGGING_GUIDELINES.md](DEBUGGING_GUIDELINES.md) for systematic troubleshooting
