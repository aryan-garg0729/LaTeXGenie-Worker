import time
import functools
from collections import defaultdict
from typing import Dict, List


class PerformanceStats:
    """Performance statistics class for collecting and displaying method execution times"""

    _stats: Dict[str, List[float]] = defaultdict(list)

    @classmethod
    def add_execution_time(cls, func_name: str, execution_time: float):
        """Add execution time record"""
        cls._stats[func_name].append(execution_time)

    @classmethod
    def get_stats(cls) -> Dict[str, dict]:
        """Get statistical results"""
        results = {}
        for func_name, times in cls._stats.items():
            results[func_name] = {
                'count': len(times),
                'total_time': sum(times),
                'avg_time': sum(times) / len(times),
                'min_time': min(times),
                'max_time': max(times)
            }
        return results

    @classmethod
    def print_stats(cls):
        """Print statistical results"""
        stats = cls.get_stats()
        print("\nPerformance Statistics:")
        print("-" * 80)
        print(f"{'Method Name':<40} {'Calls':>8} {'Total Time(s)':>12} {'Avg Time(s)':>12}")
        print("-" * 80)
        for func_name, data in stats.items():
            print(f"{func_name:<40} {data['count']:8d} {data['total_time']:12.6f} {data['avg_time']:12.6f}")


def measure_time(func):
    """Decorator to measure method execution time"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time

        # Get more detailed function identifier
        if hasattr(func, "__self__"):  # Instance method
            class_name = func.__self__.__class__.__name__
            full_name = f"{class_name}.{func.__name__}"
        elif hasattr(func, "__qualname__"):  # Class method or static method
            full_name = func.__qualname__
        else:
            module_name = func.__module__
            full_name = f"{module_name}.{func.__name__}"

        PerformanceStats.add_execution_time(full_name, execution_time)
        return result

    return wrapper