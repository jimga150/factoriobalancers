import copy
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
        return hex(self.id)[2:]

    def __copy__(self):
        cls = type(self)
        new = cls.__new__(cls)
        new.__dict__ = self.__dict__.copy()
        self.get_new_id()
        return new

    def __deepcopy__(self, memo):

        # get type of object invoking copier (this would be the child object if a child instance was copied)
        cls = type(self)

        # use __new__, and not __init__, to make a bare instance without side effects
        new = cls.__new__(cls)

        # memo stuff for deepcopy
        memo[id(self)] = new

        # populate attributes (this adapts to all attributes of the child class. yay!)
        new.__dict__ = copy.deepcopy(self.__dict__, memo)

        # custom code to ensure this object is uniquely identifiable
        self.get_new_id()

        # must return the copy
        return new

    def __hash__(self):
        return hash(self.id)