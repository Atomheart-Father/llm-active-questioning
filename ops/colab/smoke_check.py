import os, sys, json, shutil, subprocess
import importlib

def has_cuda():
    try:
        import torch
        return torch.cuda.is_available(), torch.version.cuda
    except Exception:
        return False, None

def has_mps():
    try:
        import torch
        return hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    except Exception:
        return False

def pkg_ver(name):
    try:
        m = importlib.import_module(name)
        return getattr(m, "__version__", "unknown")
    except Exception:
        return "not-installed"

def main():
    drive = None
    if "--drive" in sys.argv:
        drive = sys.argv[sys.argv.index("--drive")+1]
    ok, cuda_ver = has_cuda()
    mps = has_mps()
    report = {
        "python": sys.version,
        "cuda_available": ok,
        "cuda_version": cuda_ver,
        "mps_available": mps,
        "packages": {
            "torch": pkg_ver("torch"),
            "transformers": pkg_ver("transformers"),
            "trl": pkg_ver("trl"),
            "accelerate": pkg_ver("accelerate"),
        },
        "drive_dir": drive,
        "drive_exists": os.path.isdir(drive) if drive else False
    }
    print(json.dumps(report, indent=2))
    if drive and not os.path.isdir(drive):
        print("WARNING: Drive directory not found:", drive, file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
