class LazyTuple:
    """
    A Tuple where the elements are not evaluated
    until fetched or the tuple deconstructed.

    >>> lt = LazyTuple(lambda : 3, lambda: 4)
    >>> a, b = lt
    >>> a
    3
    >>> b
    4

    """

    def __init__(self, callback1, callback2):
        """
        :param callback1: The function to evaluate
            to get the first value
        :param callback2: The function to evaluate
            to get the second value
        """
        self.callback1 = callback1
        self.callback2 = callback2

        self._value1 = None
        self._value2 = None

    @property
    def value1(self):
        if self._value1 is None:
            self._value1 = self.callback1()
        return self._value1

    @property
    def value2(self):
        if self._value2 is None:
            self._value2 = self.callback2()
        return self._value2

    def __len__(self):
        return 2

    def __getitem__(self, key):
        if key == 0:
            return self.value1

        if key == 1:
            return self.value2
        raise KeyError(f"Lazytuple accepts key=0,1 only, got: {key}")

    def __iter__(self):
        yield self[0]
        yield self[1]

    def __str__(self):
        return f"LazyTuple({self.callback1}, {self.callback2})"

    def __repr__(self):
        return f"LazyTuple({self.callback1}, {self.callback2})"
