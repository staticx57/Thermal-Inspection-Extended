<#
.SYNOPSIS
    Builds a working pyrealsense2 for Intel RealSense L515 (L500-series LiDAR)
    support, for whichever Python is currently active on PATH.

.DESCRIPTION
    librealsense/pyrealsense2 v2.55.0+ permanently dropped L515 enumeration
    on Windows (an upstream EOL removal, not a bug that later got fixed -
    see https://github.com/realsenseai/librealsense/issues/12960), and PyPI
    no longer publishes any pre-2.55 wheel for any Python version. `pip
    install pyrealsense2` therefore cannot see an L515 no matter which
    version string you pin - confirmed live against real L515 hardware
    2026-09-18.

    D400-series cameras (D415/D435/D435i/D455/D457) are NOT affected by any
    of this - if that's what you have, just uncomment the plain
    `pyrealsense2>=2.54.0` pip pin in requirements.txt and skip this script
    entirely.

    For an L515, the only working path found was building pyrealsense2 from
    source at the last L515-supporting release (v2.54.2) against your own
    Python interpreter. This script automates exactly that build, using the
    same fix sequence confirmed working live:
      1. Shallow-clone librealsense at tag v2.54.2 to a SHORT path (its
         vendored rosbag third-party code has relative #includes that blow
         past Windows' MAX_PATH under a deeply-nested path - this is why
         -BuildRoot defaults to your user profile root, not a temp folder).
      2. Patch a missing `#include <chrono>` in src/backend.h - the 2022-era
         source relied on <thread> transitively pulling in <chrono>, which
         newer MSVC STL no longer does.
      3. Configure with CMake targeting only the `pyrealsense2` target (NOT
         `pybackend2`, which pulls in a separate libusb ExternalProject with
         its own unrelated build issue, and which this app never uses).
      4. Build with whichever installed Visual Studio has the C++ ATL
         component (mf-backend.cpp needs atlcomcli.h) - VS Build Tools'
         default "Desktop development with C++" workload does NOT include
         ATL by default; check for another VS install with it, or add the
         "C++ ATL for latest build tools" individual component via the
         Visual Studio Installer.
      5. Drop the resulting pyrealsense2.*.pyd + realsense2.dll straight
         into your active Python's site-packages, replacing any broken
         pip-installed pyrealsense2.

.PARAMETER PythonExe
    Path to the Python interpreter to build/install for. Defaults to
    whichever `python` resolves to on PATH right now.

.PARAMETER BuildRoot
    Where to clone/build librealsense. Defaults to $env:USERPROFILE\.rs_l515_build
    (short, to avoid MAX_PATH - do not point this at a deeply-nested path,
    e.g. anywhere under a long temp/session-id folder).

.PARAMETER Tag
    librealsense git tag to build. Defaults to v2.54.2 (last release before
    L515 support was removed upstream). Only change this if you've verified
    a different pre-2.55 tag also has a Python binding for your Python
    version - the exact Python versions bundled varies release to release.

.PARAMETER Clean
    Delete and re-clone BuildRoot instead of reusing an existing checkout.

.EXAMPLE
    scripts\install_realsense_l515.ps1
    Build against whatever "python" is active on PATH right now.

.EXAMPLE
    scripts\install_realsense_l515.ps1 -PythonExe "C:\Users\me\.pyenv\pyenv-win\versions\3.12.10\python.exe"
    Build against a specific interpreter (useful with pyenv/venvs).
#>
[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [string]$BuildRoot = "$env:USERPROFILE\.rs_l515_build",
    [string]$Tag = "v2.54.2",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# 0. Resolve the target Python and confirm it's really there.
# ---------------------------------------------------------------------------
Write-Step "Resolving target Python interpreter"
try {
    $resolvedPython = & $PythonExe -c "import sys; print(sys.executable)" 2>$null
} catch { $resolvedPython = $null }
if (-not $resolvedPython) {
    Write-Fail "Could not run '$PythonExe'. Pass -PythonExe <path> explicitly."
    exit 1
}
$pyVersion = & $PythonExe -c "import sys; print('%d.%d' % sys.version_info[:2])"
$pyTag = & $PythonExe -c "import sys; print('cp%d%d' % sys.version_info[:2])"
Write-Ok "Target: $resolvedPython (Python $pyVersion, wheel tag $pyTag)"

$sitePackages = & $PythonExe -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
Write-Ok "Target site-packages: $sitePackages"

# ---------------------------------------------------------------------------
# 1. Check prerequisites: git, cmake, and a Visual Studio install with ATL.
# ---------------------------------------------------------------------------
Write-Step "Checking build prerequisites (git, cmake, MSVC + ATL)"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Fail "git not found on PATH. Install Git for Windows and re-run."
    exit 1
}
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Fail "cmake not found on PATH. Install CMake and re-run."
    exit 1
}

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    Write-Fail "Visual Studio Installer (vswhere.exe) not found. Install Visual Studio / Build Tools with the 'Desktop development with C++' workload."
    exit 1
}

# Map a vswhere installationVersion major number to its CMake generator name.
$genMap = @{ "18" = "Visual Studio 18 2026"; "17" = "Visual Studio 17 2022"; "16" = "Visual Studio 16 2019" }

$vsInstances = & $vswhere -all -products '*' -format json | ConvertFrom-Json
$chosenGenerator = $null
$chosenInstallPath = $null
foreach ($inst in $vsInstances) {
    $atlProbe = Get-ChildItem -Path "$($inst.installationPath)\VC\Tools\MSVC" -Filter "atlcomcli.h" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($atlProbe) {
        $major = $inst.installationVersion.Split('.')[0]
        if ($genMap.ContainsKey($major)) {
            $chosenGenerator = $genMap[$major]
            $chosenInstallPath = $inst.installationPath
            break
        }
    }
}

if (-not $chosenGenerator) {
    Write-Fail "No installed Visual Studio has the C++ ATL component (needed for librealsense's mf-backend.cpp)."
    Write-Host ""
    Write-Host "Fix: open the Visual Studio Installer, Modify your VS/Build Tools install," -ForegroundColor Yellow
    Write-Host "and under Individual Components check 'C++ ATL for latest build tools' (or" -ForegroundColor Yellow
    Write-Host "the matching versioned ATL component), then re-run this script." -ForegroundColor Yellow
    exit 1
}
Write-Ok "Using $chosenGenerator ($chosenInstallPath) - has ATL"

# ---------------------------------------------------------------------------
# 2. Clone librealsense at the last L515-supporting tag, to a short path.
# ---------------------------------------------------------------------------
Write-Step "Preparing librealsense source at $BuildRoot"

if ($Clean -and (Test-Path $BuildRoot)) {
    Write-Warn2 "Removing existing $BuildRoot (-Clean)"
    Remove-Item -Recurse -Force $BuildRoot
}

$srcDir = Join-Path $BuildRoot "src"
$buildDir = Join-Path $BuildRoot "build"

if (-not (Test-Path $srcDir)) {
    New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
    git clone --depth 1 --branch $Tag https://github.com/realsenseai/librealsense.git $srcDir
    if ($LASTEXITCODE -ne 0) { Write-Fail "git clone failed."; exit 1 }
    Push-Location $srcDir
    git config core.longpaths true
    Pop-Location
    Write-Ok "Cloned $Tag into $srcDir"
} else {
    Write-Ok "Reusing existing checkout at $srcDir (pass -Clean to force a fresh clone)"
}

# ---------------------------------------------------------------------------
# 3. Patch the missing <chrono> include (newer MSVC STL stopped pulling it
#    in transitively via <thread>, breaking std::chrono::system_clock::now()
#    in backend.h - confirmed live 2026-09-18 with MSVC 14.44/14.51).
# ---------------------------------------------------------------------------
Write-Step "Patching missing <chrono> include in src/backend.h"

$backendH = Join-Path $srcDir "src\backend.h"
$backendContent = Get-Content -Raw $backendH
if ($backendContent -notmatch '#include <chrono>') {
    $backendContent = $backendContent -replace `
        '#include <thread>       // For this_thread::sleep_for', `
        "#include <thread>       // For this_thread::sleep_for`n#include <chrono>       // For system_clock::now() - no longer pulled in transitively by <thread>"
    Set-Content -Path $backendH -Value $backendContent -NoNewline
    Write-Ok "Patched backend.h"
} else {
    Write-Ok "backend.h already has <chrono> (already patched)"
}

# ---------------------------------------------------------------------------
# 4. Configure - only the pyrealsense2 target, not pybackend2 (which drags
#    in a separate broken libusb ExternalProject this app doesn't need).
# ---------------------------------------------------------------------------
Write-Step "Configuring CMake build"

$pythonForCMake = $resolvedPython -replace '\\', '/'
# NOTE: every -DNAME=value token below is individually double-quoted. Passed
# bare, PowerShell's native-argument marshalling splits a token like
# "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" into TWO argv entries ("...=3" and
# ".5"), silently truncating the value to "3" - confirmed live 2026-09-18.
# Quoting the whole "-D...=..." token keeps it intact as one argv entry.
cmake -S $srcDir -B $buildDir -G $chosenGenerator -A x64 `
    "-DCMAKE_POLICY_VERSION_MINIMUM=3.5" `
    "-DBUILD_PYTHON_BINDINGS=ON" `
    "-DPYTHON_EXECUTABLE=$pythonForCMake" `
    "-DBUILD_EXAMPLES=OFF" "-DBUILD_GRAPHICAL_EXAMPLES=OFF" "-DBUILD_UNIT_TESTS=OFF" `
    "-DCHECK_FOR_UPDATES=OFF" "-DCMAKE_BUILD_TYPE=Release"
if ($LASTEXITCODE -ne 0) { Write-Fail "CMake configure failed."; exit 1 }
Write-Ok "Configured"

# ---------------------------------------------------------------------------
# 5. Build. This is the slow step (full librealsense core + bindings) -
#    expect 10-30+ minutes depending on the machine.
# ---------------------------------------------------------------------------
Write-Step "Building pyrealsense2 (this compiles the full librealsense core - can take 10-30+ minutes)"

cmake --build $buildDir --config Release --target pyrealsense2 -- -m
if ($LASTEXITCODE -ne 0) { Write-Fail "Build failed - see errors above."; exit 1 }
Write-Ok "Build succeeded"

# ---------------------------------------------------------------------------
# 6. Install into the target Python's site-packages.
# ---------------------------------------------------------------------------
Write-Step "Installing into $sitePackages"

$pydPath = Get-ChildItem -Path (Join-Path $buildDir "Release") -Filter "pyrealsense2*.pyd" -ErrorAction SilentlyContinue | Select-Object -First 1
$dllPath = Join-Path $buildDir "Release\realsense2.dll"

if (-not $pydPath -or -not (Test-Path $dllPath)) {
    Write-Fail "Build succeeded but couldn't find pyrealsense2*.pyd / realsense2.dll under $buildDir\Release."
    exit 1
}

try {
    & $PythonExe -m pip uninstall -y pyrealsense2 2>&1 | Out-Null
} catch {
    # Not installed yet, or pip printed a warning to stderr - either way
    # there's nothing to clean up, so just move on.
}

try {
    Copy-Item $pydPath.FullName -Destination $sitePackages -Force -ErrorAction Stop
    Copy-Item $dllPath -Destination $sitePackages -Force -ErrorAction Stop
} catch {
    if ($_.Exception.Message -match "being used by another process") {
        Write-Fail "Can't overwrite pyrealsense2 in site-packages - it's loaded by a running process."
        Write-Host "Close any running 'python -m thermal_inspection' (or other Python process" -ForegroundColor Yellow
        Write-Host "that imported pyrealsense2) and re-run this script." -ForegroundColor Yellow
        exit 1
    }
    throw
}
Write-Ok "Copied $($pydPath.Name) and realsense2.dll into site-packages"

# ---------------------------------------------------------------------------
# 7. Verify: module imports and the native context object constructs
#    cleanly. (Can't verify device enumeration here without hardware
#    plugged in - that's on you to confirm once the app is running.)
# ---------------------------------------------------------------------------
Write-Step "Verifying import"

$verify = & $PythonExe -c "import pyrealsense2 as rs; ctx = rs.context(); print('pyrealsense2 imported OK, context() constructed OK')" 2>&1
Write-Host $verify
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Import verification failed - see output above."
    exit 1
}

Write-Host ""
Write-Ok "L515-compatible pyrealsense2 installed for $resolvedPython"
Write-Host "Next: connect the L515 and run 'python -m thermal_inspection' - check the" -ForegroundColor Cyan
Write-Host "Cameras tab / console log for 'Found RealSense device: Intel RealSense L515'." -ForegroundColor Cyan
