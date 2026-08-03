import threading
import time

threadLock = threading.Lock()
unique_idx = 0
copy_delay = 0

class UniqueIDObj:
    def __init__(self):
        self.id = None
        self.get_new_id()

    def get_new_id(self):
        with threadLock:
            global unique_idx
            self.id = unique_idx
            if copy_delay > 0:
                time.sleep(copy_delay)
            unique_idx += 1

    def __str__(self):
        return str(self.id)

    def __setstate__(self, state):
        # called when this object is copied
        self.__dict__.update(state)
        self.get_new_id()

    def __hash__(self):
        return hash(id(self))