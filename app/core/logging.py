import logging, sys

def setup_logging(level: str = "INFO"):
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)
    h = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    h.setFormatter(fmt)
    root.addHandler(h)
