from functools import lru_cache, wraps
import threading


MODEL_EXECUTION_LOCK = threading.RLock()


def serialized_model_work(function):
    @wraps(function)
    def execute(*args, **kwargs):
        with MODEL_EXECUTION_LOCK:
            return function(*args, **kwargs)
    return execute


def single_instance(factory):
    cached = lru_cache(maxsize=1)(factory)
    lock = threading.RLock()

    @wraps(factory)
    def get(*args, **kwargs):
        with lock:
            return cached(*args, **kwargs)

    def clear():
        with lock:
            cached.cache_clear()

    get.cache_clear = clear
    get.cache_info = cached.cache_info
    return get
