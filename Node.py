import threading
import time

threadLock = threading.Lock()
node_idx = 0
copy_delay = 0

class Node:
    def __init__(self):
        self.name = ""
        self.id = None
        self.get_new_id()

    def get_new_id(self):
        with threadLock:
            global node_idx
            self.id = node_idx
            if copy_delay > 0:
                time.sleep(copy_delay)
            node_idx += 1

    def __str__(self):
        if self.name != "":
            return self.name
        # return hex(hash(self))[-4:]
        return str(self.id)

    def __copy__(self):
        ans = Node()
        ans.name = self.name
        return ans

    def __deepcopy__(self, memo):
        return self.__copy__()

    def __hash__(self):
        return hash(str(id(self)))