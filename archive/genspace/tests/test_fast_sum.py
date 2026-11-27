import itertools
import unittest
import numpy as np
from src.fast_exact import _compensated_add

class CompensatedSumTests(unittest.TestCase):
    def test_exact_binary64_for_six_cell_quality_sequences(self):
        for values in itertools.product((0., .4, .6, .8), repeat=6):
            high=np.array([0.]); low=np.array([0.])
            for value in values: high,low=_compensated_add(high,low,np.array([value]))
            self.assertEqual(float(high[0]+low[0]).hex(),sum(values).hex(),values)

if __name__ == '__main__': unittest.main()
