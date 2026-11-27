"""Read-only check of the arithmetic in S12. Run with Python 3.11 or newer.

The inputs are scalar limit cases and the paper's fixed public constants.
No serialized benchmark, new instance, RNG, solver, or external package is used.
"""

from fractions import Fraction
from itertools import product
import json
import math
import sys


def require(condition, note):
    if not condition:
        raise ArithmeticError(note)


class Arithmetic:
    def __init__(self):
        self.operations = 0

    def add(self, left, right):
        self.operations += 1
        return left + right

    def sub(self, left, right):
        self.operations += 1
        return left - right

    def mul(self, left, right):
        self.operations += 1
        return left * right

    def div(self, left, right):
        self.operations += 1
        return left / right

    def fold(self, values):
        total = 0.0
        for value in values:
            total = self.add(total, value)
        return total


def terms(capacities, demand):
    z = tuple((d - c) / max(c, 1.0e-9) for c, d in zip(capacities, demand, strict=True))
    require(all(math.isfinite(x) and -1.0 <= x < 2**30 for x in z), "Normalized term range")
    return tuple(max(x, 0.0) for x in z), tuple(max(-1.0, min(-x, 1.0)) for x in z)


def flat(ops, rows, quality, costs, group):
    v = ops.div(ops.fold(v for row in rows for v in row[0]), 18.0)
    m = ops.div(ops.fold(m for row in rows for m in row[1]), 18.0)
    q = ops.div(ops.fold(quality), 6.0)
    a = ops.div(ops.fold(costs), 6.0)
    out = ops.sub(v, ops.mul(0.025, m))
    out = ops.add(out, ops.mul(0.02, a))
    out = ops.add(out, ops.mul(0.08, ops.sub(1.0, q)))
    return ops.add(out, ops.mul(0.01, group))


def local(ops, row, quality):
    v, m = row
    vx = ops.div(ops.add(ops.add(v[0], v[1]), v[2]), 18.0)
    mx = ops.div(ops.mul(0.025, ops.add(ops.add(m[0], m[1]), m[2])), 18.0)
    qx = ops.div(ops.mul(0.08, quality), 6.0)
    return ops.sub(ops.sub(vx, mx), qx)


def jointly(ops, local_values, costs, group):
    start = ops.fold(local_values)
    execution = ops.mul(0.02, ops.div(ops.fold(costs), 6.0))
    tail = ops.add(ops.add(execution, 0.08), ops.mul(0.01, group))
    return ops.add(start, tail)


def real_flat(rows, quality, costs, group):
    v = sum(Fraction(v) for row in rows for v in row[0]) / 18
    m = sum(Fraction(m) for row in rows for m in row[1]) / 18
    q = sum(map(Fraction, quality)) / 6
    a = sum(map(Fraction, costs)) / 6
    return v - Fraction(0.025) * m + Fraction(0.02) * a + Fraction(0.08) * (1 - q) + Fraction(0.01) * group


def main():
    require(sys.float_info.radix == 2 and sys.float_info.mant_dig == 53 and
            sys.float_info.max_exp == 1024 and sys.float_info.rounds == 1, "Binary64 nearest rounding required")
    require(1.0 + 2.0**-53 == 1.0 and math.ulp(0.0) == 2.0**-1074, "Expected ties-to-even and subnormal support")

    # Original registry, in sorted role order. The third role adds EDGE=0.1.
    execution_cost = (0.02,) * 3 + (0.01,) * 9
    costs = tuple(sum(execution for bit, execution in enumerate(execution_cost) if mask & (1 << bit))
                  + (0.1 if mask & 4 else 0.0) for mask in range(1 << 12))
    amax = costs[-1]
    require(all(0.0 <= c < 1.0 and c <= amax for c in costs), "Role bound")
    profiles = [(0.0, (0.0, 0.0, 0.0))]
    for q, rate in product((0.4, 0.6, 0.8), (0.5, 0.75, 1.0)):
        fh = rate * 0.4
        profiles.extend(((q, (q, fh, 0.0)), (q, (q * 0.5, fh * 0.7, q * 0.5))))

    epsilon = 1.0e-9
    capacities = (0.0, math.ulp(0.0), sys.float_info.min, math.nextafter(epsilon, 0.0), epsilon,
                  math.nextafter(epsilon, math.inf), 0.1, 0.168, math.nextafter(0.4, 0.0), 0.4,
                  math.nextafter(0.4, math.inf), 0.8, 0.96, 1.0, 2.0**500, sys.float_info.max)
    u = Fraction(1, 2**53)
    eta = Fraction(1, 2**1075)
    gamma = 128 * u / (1 - 128 * u)
    subnormal_error = 128 * (1 + u)**128 * eta
    require(2 * gamma + 2 * u < Fraction(1, 2**44), "Rounding margin identity")
    require((2 * subnormal_error + eta) / 32 < u, "Subnormal budget identity")

    scalar_order_checks = 0
    for cap in capacities:
        for pos in range(3):
            demands = sorted({p[1][pos] for p in profiles})
            for small, large in zip(demands, demands[1:]):
                a = terms((cap,), (small,))
                b = terms((cap,), (large,))
                require(a[0][0] <= b[0][0] and a[1][0] >= b[1][0], "Public-resource monotonicity")
                scalar_order_checks += 1

    path_checks = 0
    for start in range(len(capacities)):
        caps = tuple(tuple(capacities[(start + 3*j + k) % len(capacities)] for k in range(3)) for j in range(6))
        tables = [[terms(c, p[1]) for p in profiles] for c in caps]
        zmax = max(v for cell in tables for item in cell for v in item[0])
        scale = 32 + 32 * Fraction(zmax) + 12 * Fraction(amax)
        allowance = (2.0**-38) * ((32.0 + 32.0 * zmax) + 12.0 * amax)
        require(Fraction(1, 2**39) * scale <= Fraction(allowance) < scale, "Rounded allowance")
        error = gamma * scale + subnormal_error

        for alternative in range(len(profiles)):
            chosen = tuple((alternative + 3*j) % len(profiles) for j in range(6))
            masks = tuple((117*alternative + 31*j + start) % len(costs) for j in range(6))
            actual_costs = [costs[m] if p else 0.0 for m, p in zip(masks, chosen, strict=True)]
            g = (alternative + start) % 5
            actual = [tables[j][p] for j, p in enumerate(chosen)]
            quality = [profiles[p][0] for p in chosen]
            first, second = Arithmetic(), Arithmetic()
            f = flat(first, actual, quality, actual_costs, g)
            jh = jointly(second, [local(second, t, q) for t, q in zip(actual, quality, strict=True)], actual_costs, g)
            real = real_flat(actual, quality, actual_costs, g)
            require(first.operations == 61 and second.operations == 84, "Operation counts")
            require(abs(Fraction(f) - real) <= error and abs(Fraction(jh) - real) <= error, "Common expansion error")

            options = [sorted({p, 0, (p+1) % len(profiles), (2*p+1) % len(profiles)}) for p in chosen]
            demand_min = [tuple(min(profiles[p][1][k] for p in opts) for k in range(3)) for opts in options]
            quality_max = [max(profiles[p][0] for p in opts) for opts in options]
            lower_cost = [min(cost, costs[mask & 17]) for cost, mask in zip(actual_costs, masks, strict=True)]
            group_min = max(0, g - 1)
            coordinate = flat(Arithmetic(), [terms(c, d) for c, d in zip(caps, demand_min, strict=True)],
                              quality_max, lower_cost, group_min)
            ja = jointly(Arithmetic(), [min(local(Arithmetic(), tables[j][p], profiles[p][0]) for p in opts)
                                         for j, opts in enumerate(options)], lower_cost, group_min)
            require(coordinate <= f and ja <= jh and ja - allowance <= f, "Completion lower bound")
            path_checks += 1

    print(json.dumps({"status": "PASS", "path_checks": path_checks, "scalar_order_checks": scalar_order_checks,
                      "role_masks": len(costs), "complete_ops": 61, "joint_uncorrected_ops": 84,
                      "scope": "static arithmetic only"}, indent=2))


if __name__ == "__main__":
    main()
