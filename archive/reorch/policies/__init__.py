from .all_sequential import AllSequential
from .all_concurrent import AllConcurrent
from .static_cluster import StaticCluster
from .optimal_static import OptimalStaticPartition
from .online_sequential import OnlineSequentialReschedule
from .runtime_oracle import RuntimeRepartitionOracle

POLICIES = {
    "B0": AllSequential,
    "B1": AllConcurrent,
    "B2": StaticCluster,
    "B3": OptimalStaticPartition,
    "B4": OnlineSequentialReschedule,
    "O1": RuntimeRepartitionOracle,
}
