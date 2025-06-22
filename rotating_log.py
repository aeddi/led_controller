import os, time
from logging import Handler
from ustrftime import strftime

class RotatingFileHandler(Handler):
    def __init__(self, filename, maxBytes=0, backupCount=0):
        super().__init__()
        self.filename = filename
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.terminator = "\n"
        try:
            self._current_filesize = os.stat(self.filename)[6]
        except OSError:
            self._current_filesize = 0

    def __format_filename(self, count):
      if count > 0:
        return self.filename + ".{0}".format(count)
      return self.filename

    def emit(self, record):
        if record.levelno < self.level:
            return

        # Format the log entry
        entry = self.format(record) + self.terminator

        # Check if the entry exceeds the maximum bytes allowed
        if self.maxBytes and self._current_filesize + len(entry) > self.maxBytes:

            # Rotate the backup files
            if self.backupCount > 0:
                for i in range(self.backupCount - 1, -1, -1):
                    try:
                        os.rename(
                            self.__format_filename(i),
                            self.__format_filename(i + 1),
                        )
                    except OSError:
                        pass

            # If no backups, just remove the current file
            else:
                try:
                    os.remove(self.filename)
                except OSError:
                    pass

            # Reset the counter
            self._current_filesize = 0

        # Write the log entry to the file
        with open(self.filename, "a") as f:
            f.write(entry)

        # Update the counter
        self._current_filesize += len(entry)

# Copied from the original MicroPython code, but modified to use 
# https://github.com/iyassou/ustrftime/tree/main
class Formatter:
    def __init__(self, fmt=None, datefmt="%Y-%m-%d %H:%M:%S"):
        self.fmt = _default_fmt if fmt is None else fmt
        self.datefmt = datefmt

    def usesTime(self):
        return "asctime" in self.fmt

    def formatTime(self, datefmt, record):
        return strftime(datefmt, time.localtime(record.ct))

    def format(self, record):
        if self.usesTime():
            record.asctime = self.formatTime(self.datefmt, record)
        return self.fmt % {
            "name": record.name,
            "message": record.message,
            "msecs": record.msecs,
            "asctime": record.asctime,
            "levelname": record.levelname,
        }