from importlib.metadata import PackageNotFoundError, version

try:
    version = version("RoffIO")
except PackageNotFoundError:
    version = "0.0.0"
