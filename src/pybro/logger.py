# logger.py – zero‑dependency, bit‑flag controlled logger
import sys
import os

DEBUG = 1
INFO = 2
WARN = 4
ERROR = 8

_LEVEL_NAMES = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARN: "WARN",
    ERROR: "ERROR",
}

class Logger:
    def __init__(self, level=INFO | WARN | ERROR, logfile=None):
        self.level = level
        self.file = None
        if logfile:
            os.makedirs(os.path.dirname(logfile) or '.', exist_ok=True)
            self.file = open(logfile, 'a', encoding='utf-8')

    def _log(self, msg_level, msg):
        if not (self.level & msg_level):
            return
        level_name = _LEVEL_NAMES.get(msg_level, "?")
        text = f"[{level_name}] {msg}"
        print(text, file=sys.stderr)
        if self.file:
            self.file.write(text + '\n')
            self.file.flush()

    def debug(self, msg):
        self._log(DEBUG, msg)

    def info(self, msg):
        self._log(INFO, msg)

    def warn(self, msg):
        self._log(WARN, msg)

    def error(self, msg):
        self._log(ERROR, msg)

    def set_level(self, level):
        self.level = level

    def set_level_from_string(self, s):
        """Accept comma-separated level names, e.g., 'debug,info'."""
        mapping = {
            'debug': DEBUG,
            'info': INFO,
            'warn': WARN,
            'error': ERROR,
        }
        level = 0
        for part in s.split(','):
            part = part.strip().lower()
            if part in mapping:
                level |= mapping[part]
        if level:
            self.level = level

    def close(self):
        if self.file:
            self.file.close()
            self.file = None