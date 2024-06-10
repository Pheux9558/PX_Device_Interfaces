import time


class Timer:
    def __init__(self):
        self.total: float = 0
        self.start_tm: int = 0

    def start(self):
        self.start_tm = time.time()

    def stop(self, operations=0) -> float:
        if not self.start_tm == 0:
            self.total = time.time() - self.start_tm
            print(f'Total time: {'{0:.10f}'.format(self.total)}')
            if operations > 0:
                print(f'Time per operation: {self.total / operations}')
            return self.total
