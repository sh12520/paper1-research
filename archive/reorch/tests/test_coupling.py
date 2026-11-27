import unittest
from config import generate_instance
from coupling import coupling_score

class CouplingTests(unittest.TestCase):
    def test_shift_emerges_from_profiles(self):
        x = generate_instance(1, 'COUPLING_SHIFT', 'strong', 'medium')
        def score(a, b, ka=0):
            return coupling_score(x.profiles[a][ka], x.profiles[b][0], x.capacity,
                                  x.deadlines[a], x.deadlines[b])
        self.assertGreater(score('A','B'), score('A','C'))
        self.assertGreater(score('A','C',2), score('A','C',0))

    def test_control_profile_direction_stays_constant(self):
        x = generate_instance(1, 'STATIC_COUPLING', 'strong', 'medium')
        for profiles in x.profiles.values():
            for p in profiles[1:]:
                ratios = [p.demand[i] / profiles[0].demand[i] for i in range(3)]
                self.assertLess(max(ratios)-min(ratios), .001)

if __name__ == '__main__': unittest.main()
