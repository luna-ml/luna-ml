from io import BytesIO
from datetime import datetime
from urllib.parse import urlparse
import shutil
import os
import glob

class FileStat:
    def __init__(self, path, size=0, etag=None, lastModified=None):
        self.path = path # relative path from the storage base
        self.size = size
        self.etag = etag
        self.lastModified = lastModified

class LocalFsStorage():
    def __init__(self, basePath):
        self._basePath = basePath

    def _fsAbsPath(self, path):
        if self._basePath == None:
            return f"""/{path.lstrip("/")}"""

        basePath = self._basePath.lstrip("/").rstrip("/")
        filePath = path.lstrip("/")
        return f"/{basePath}/{filePath}"

    def put(self, file, targetPath):
        absPath = self._fsAbsPath(targetPath)
        os.makedirs(os.path.dirname(absPath), exist_ok=True)

        with open(self._fsAbsPath(targetPath), "wb") as w:
            shutil.copyfileobj(file, w)

    def get(self, targetPath):
        absPath = self._fsAbsPath(targetPath)
        f = open(absPath, "rb")
        return f, self.stat(targetPath)

    def stat(self, targetPath):
        stat = os.stat(self._fsAbsPath(targetPath))

        return FileStat(
            path=targetPath,
            size=stat.st_size,
            etag=self.__etag(stat, targetPath),
            lastModified=datetime.utcfromtimestamp(int(stat.st_mtime))
        )

    def __etag(self, stat, path) -> str:
        return f"{stat.st_size}-{stat.st_mtime}-{path}"

    def list(self, targetPath):
        fileList = []
        basePath = self._fsAbsPath("").rstrip("/")
        absPath = self._fsAbsPath(targetPath)
        for path in glob.glob(f"{absPath}/**", recursive=True):
            if not os.path.isfile(path):
                continue

            stat = os.stat(path)
            fileList.append(FileStat(
                path=path[len(basePath):],
                size=stat.st_size,
                etag=self.__etag(stat, path),
                lastModified=datetime.utcfromtimestamp(int(stat.st_mtime))
            ))

        return fileList
