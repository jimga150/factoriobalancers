import datetime
import time

class ProgressPrinter:

    def __init__(self, min_progress_check: float = 0.1, min_time_check_s: int = 10):
        self.progress_bookmarks = []
        self.time_bookmarks = []
        self.min_progress_check = min_progress_check
        self.min_time_check_s= min_time_check_s
        self.first_bookmark_recorded = False

    def print_progress(self, completion_fraction: float):
        curr_time = time.time()

        if not self.first_bookmark_recorded:

            self.first_bookmark_recorded = True
            self.record_bookmark(completion_fraction, curr_time)
            return

        if completion_fraction >= 1:
            td_str = str(datetime.timedelta(seconds=(curr_time - self.time_bookmarks[0])) // 1000000 * 1000000)
            print(f"Took {td_str} seconds to complete. Completed at {time.ctime(curr_time)}")
            return

        if curr_time - self.time_bookmarks[-1] > self.min_time_check_s or \
                completion_fraction - self.progress_bookmarks[-1] > self.min_progress_check:

            self.record_bookmark(completion_fraction, curr_time)

            elapsed = curr_time - self.time_bookmarks[0]
            est_total_time = elapsed / completion_fraction
            est_remaining_time = est_total_time - elapsed

            est_remaining_time_str = str(datetime.timedelta(seconds=est_remaining_time) // 1000000 * 1000000)

            eta = curr_time + est_remaining_time
            eta_str = time.ctime(eta)

            print(f"{completion_fraction * 100:>6.2f}% done, "
                  f"{est_remaining_time_str} remaining; "
                  f"Estimated completion {eta_str}")

    def record_bookmark(self, completion_frac: float, time_s: float):
        self.progress_bookmarks.append(completion_frac)
        self.time_bookmarks.append(time_s)