

def memoize (max_cache_size=1000):
    """Python 2.4 compatible memoize decorator.
    It creates a cache that has a maximum size.  If the cache exceeds the max,
    it is thrown out and a new one made.  With such behavior, it is wise to set
    the cache just a little larger that the maximum expected need.

    Parameters:
      max_cache_size - the size to which a cache can grow

    Limitations:
      The cache works only on args, not kwargs
    """
    def wrapper (f):
        def fn (*args):
            try:
                return fn.cache[args]
            except KeyError:
                if fn.count >= max_cache_size:
                    fn.cache = {}
                    fn.count = 0
                fn.cache[args] = result = f(*args)
                fn.count += 1
                return result
        fn.cache = {}
        fn.count = 0
        return fn
    return wrapper