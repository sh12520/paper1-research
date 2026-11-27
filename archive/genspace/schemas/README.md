# Public schemas

`contract.schema.json` specifies the JSON representation of the recursive
typed AST. Every clause has the discriminant `type`, followed by the fields of
the corresponding dataclass in `src/models.py`; tuples serialize as arrays.
`capability.schema.json` describes one registry entry. JSON Schema checks shape
and primitive domains; runtime validation must additionally enforce configured
depth and finite value domains, interval ordering, capability preconditions,
semantic rules, physical feasibility, acceptance, and compilation. Neither
schema establishes that a contract is executable or agreed.
