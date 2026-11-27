# Admissible FLAT score bounds for partial contracts

The search uses the existing public contract language at the declared depth. The exact-score path applies the original `FLAT-FEASIBILITY` proxy from `results/method_dev_v1/public_search.py`. No public feasibility, acceptance, utility or proposal results enter either bound. The term-by-term envelope is defined in `PARTIAL_CONTRACT_ABSTRACT_SEMANTICS.md`.

## Exact public score and coordinatewise bound

For each ordered cell `j` and resource `r`, let `x[j,r]` be the FLAT demand, `C[j,r]` the capacity and `D[j,r]=max(C[j,r],1e-9)`. Let `z=(x-C)/D`. FLAT sums `max(z,0)` and `clip(-z,-1,1)` in the six-cell, RAN/FH/EDGE order and divides each total by 18. This yields the violation `v` and margin `m`. The six-cell averages `q` and `a` are respectively quality and public execution plus resource cost from the active runtime-role set. Idle cells have zero demand, quality and cost. The group count `g` refers to the normalized whole-footprint groups used by FLAT. The final ordered binary64 expression is

```text
v - 0.025*m + 0.02*a + 0.08*(1-q) + 0.01*g
```

The score implementations use the frozen sequence of additions, the same parenthesization of the FH offload demand and the same role summation order. The comparator recomputes original scores using NumPy's original `_proxy` and checks candidate score bits directly.

- **Violation.** Each envelope demand minimum is no larger than the corresponding completion demand. Division by the fixed positive `D` and application of the positive part are monotone. The resulting violation is a lower bound.
- **Margin term.** Using that same minimum gives an upper bound on `clip(-z,-1,1)`. Its negative coefficient gives a lower bound on the score contribution.
- **Capability cost.** Idle-possible cells give a zero lower bound in this nonnegative registry. Otherwise every active role set contains the cell's mandatory roles. A finite role-mask lattice supplies the smallest exact cost over their supersets. Sequential addition and division by six preserve the inequality.
- **Quality.** Per-cell quality maxima summed in the original sequence give an upper bound on `q`. Thus `0.08*(1-q_max)` bounds the quality penalty from below.
- **Mechanism groups.** Groups in the mandatory whole-contract footprint survive every completion, including any possible IF collapse. Their count is a lower bound. Binding and depth are handled in the grammar. The search removes a subtree only when its group envelope proves it has no member in FLAT's structural domain, which allows one or two groups. The static B2 route is separate.

The same monotonicity applies to finite correctly rounded binary64 operations in the prescribed order. The coordinatewise bound therefore needs no downward tolerance. Every scored leaf checks its lower bound against the actual score.

## Optional stronger bound from joint cell choices

The cell envelope retains two bitsets of possible profile IDs, one per offload level, plus an idle flag. For each allowed cell state evaluate the three resource violation terms, three margin terms and its quality. Expressions here start from the same rounded resource terms the exact scorer uses. For this paragraph the arithmetic expression is first interpreted over the reals:

```text
cell(j,state) = sum(v_terms)/18 - 0.025*sum(m_terms)/18 - 0.08*quality/6
joint_bound = sum_j min_allowed_state(cell(j,state)) + 0.02*a_min + 0.08 + 0.01*g_min
```

The set at each cell contains the state of any completion. Independent minimization over those sets is a relaxation. The cost and group lower bounds preserve the inequality after summing. This expression is tighter when, for example, maximum quality is achievable only by an active cell, while the minimum resource use comes from an idle completion.

Reassociation is used for this bound only. Let `V` be the largest finite violation component over the query's profile/offload table and six cells, and let `A` be the cost of the full frozen nonnegative role mask. The scale `32 + 32*V + 12*A` dominates the absolute sum of the expression inputs after their coefficients in either evaluation tree. Each summation, division and weighting expression contains fewer than 128 binary64 rounded operations. The standard forward bound for summations of signed terms is `gamma_128` times the absolute weighted input sum, with `u=2^-53` and `gamma_n = n*u/(1-n*u)`. The implemented downward allowance `2^-38*(32 + 32*V + 12*A)` exceeds the sum of the roundoff bounds for the exact and joint evaluation trees. It also covers rounding of the allowance calculation and subtraction on the finite benchmark domain. The score literals denote the same binary64 constants in both expressions. The returned bound is the maximum of the coordinatewise bound and this corrected joint bound. Nonfinite results fail closed.

## Output and tie certificate

The open heap contains partial contracts and unprocessed complete leaves, each with a safe lower bound. The second heap contains normalized unique signatures keyed by `(exact_score, signature_bytes)`. An entry is emitted only when the first heap is empty or its minimum bound is **strictly greater** than the exact score. Thus all legal derivations with equal or better score, including possible duplicates of the candidate, have been resolved. The strict check is conservative when it could be shown that a tie cannot yield a smaller signature.

For the existing depth≤2 reference graph, class IDs are contiguous positions in lexicographically sorted compact signatures. The byte ordering therefore gives exactly the same tie ordering, and the independent comparator translates a sealed signature to the actual numeric ID. The search does not compute or query graph ranks. The class's smallest raw `syntax_key` is retained until emission and normalized with the existing interpreter. At depth one this is the comparator's lexical rule. At depth two the existing graph's tokens order by operator, parameter and lexical ranks of the depth-one child witnesses. For the fixed operator domains these order the same text fields. Compact depth-one equivalence checks establish the unique normalized child form for each signature used in those tokens. The independent protocol audit still checks the selected representative explicitly. Depth three, if authorized by the depth≤2 gate, has no external graph tie ID. It uses the same signature order and certifies a prefix by the frontier rule.

The profile-hole refinements partition the original finite profile domain by quality, then rate, then deadline where needed. The union of subdomains remains exactly the original set, including all values whose scores tie. This changes queue branching without enumerating the descendants of a clause hole.

## Claim boundary

Top-down partial-program search, hole filling, best-first search and admissible bounds from abstract interpretation are established techniques. This engineering gate concerns the contract-specific time, state and resource envelope, capability constraints, compatibility with the FLAT order and consumption by the existing bilateral protocol. It provides no priority or novelty claim.
