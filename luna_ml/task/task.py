import uuid
import threading
from datetime import datetime

class Task():
    def __init__(self,
                 taskId: int,
                 image: str, # list of images
                 command: list, # corresponding list of 'command list' for each images.
                 copyToContainerBeforeStart=[],  # list of tuple (srcDirOnStorage, dstDirOnContainerFs)
                 copyFromContainerAfterFinish=[] # list of tuple (srcDirOnContainerFs, dstDirOnStorage)
    ):
        self.id = taskId
        self.image = image
        self.command = command
        self.copyToContainerBeforeStart = copyToContainerBeforeStart
        self.copyFromContainerAfterFinish = copyFromContainerAfterFinish
