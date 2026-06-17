import multiprocessing
import queue
from uuid import uuid4

from backend.services.erosion_model import WindErosionSimulator

SUPPORTED_METHODS = frozenset({
    "simulate_two_phase_flow",
    "simulate_two_phase_flow_with_des",
    "calculate_friction_velocity",
    "calculate_threshold_friction_velocity",
    "calculate_sand_transport_rate",
    "calculate_wind_energy",
    "calculate_particle_impact_energy",
})


class TwoPhaseFlowWorker(multiprocessing.Process):
    def __init__(self, task_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue):
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        simulator = WindErosionSimulator()
        while True:
            try:
                task = self.task_queue.get()
            except (EOFError, OSError):
                break
            if task is None:
                break
            task_id = task.get("task_id", "")
            method = task.get("method", "")
            kwargs = task.get("kwargs", {})
            if method not in SUPPORTED_METHODS:
                self.result_queue.put({
                    "task_id": task_id,
                    "result": None,
                    "error": f"Unsupported method: {method}",
                })
                continue
            try:
                func = getattr(simulator, method)
                result = func(**kwargs)
                self.result_queue.put({
                    "task_id": task_id,
                    "result": result,
                    "error": None,
                })
            except Exception as exc:
                self.result_queue.put({
                    "task_id": task_id,
                    "result": None,
                    "error": str(exc),
                })


class TwoPhaseFlowWorkerPool:
    def __init__(self, num_workers: int = None):
        if num_workers is None:
            num_workers = multiprocessing.cpu_count()
        self.num_workers = num_workers
        self.task_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.result_queue: multiprocessing.Queue = multiprocessing.Queue()
        self._workers: list[TwoPhaseFlowWorker] = []
        self._pending: dict[str, multiprocessing.Event] = {}
        self._results: dict[str, dict] = {}

    def start(self):
        for _ in range(self.num_workers):
            w = TwoPhaseFlowWorker(self.task_queue, self.result_queue)
            w.start()
            self._workers.append(w)

    def submit(self, method: str, kwargs: dict = None) -> str:
        if kwargs is None:
            kwargs = {}
        task_id = uuid4().hex
        self.task_queue.put({
            "task_id": task_id,
            "method": method,
            "kwargs": kwargs,
        })
        return task_id

    def get_result(self, task_id: str, timeout: float = 30) -> dict:
        if task_id in self._results:
            return self._results.pop(task_id)
        deadline = timeout
        while deadline > 0:
            try:
                result = self.result_queue.get(timeout=min(1.0, deadline))
                if result["task_id"] == task_id:
                    return result
                self._results[result["task_id"]] = result
                deadline -= 1.0
            except queue.Empty:
                deadline -= 1.0
        return {
            "task_id": task_id,
            "result": None,
            "error": f"Timeout waiting for result (task_id={task_id})",
        }

    def shutdown(self):
        for _ in self._workers:
            try:
                self.task_queue.put(None)
            except (OSError, ValueError):
                pass
        for w in self._workers:
            w.join(timeout=5)
            if w.is_alive():
                w.terminate()
        self._workers.clear()
        self._results.clear()


if __name__ == "__main__":
    pool = TwoPhaseFlowWorkerPool(num_workers=2)
    pool.start()
    try:
        tid1 = pool.submit("calculate_friction_velocity", {"wind_speed": 10.0})
        r1 = pool.get_result(tid1, timeout=10)
        print(f"friction_velocity: {r1}")

        tid2 = pool.submit("simulate_two_phase_flow", {
            "wind_speed": 8.0,
            "wind_direction": 45.0,
            "surface_hardness": 0.7,
            "soil_moisture": 0.1,
            "duration_hours": 1.0,
            "grid_resolution": 5,
        })
        r2 = pool.get_result(tid2, timeout=30)
        print(f"two_phase_flow keys: {list(r2.get('result', {}).keys()) if r2.get('result') else r2}")
    finally:
        pool.shutdown()
