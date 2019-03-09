from collections import defaultdict
from typing import Dict

import numpy as np

import hypothesis.strategies as st
import hypothesis.extra.numpy as hnp

from liveplot.typing import LiveMetrics

names = ["metric_a", "metric_b", "metric_c"]


def finite_array(size):
    return hnp.arrays(shape=(size,),
                      dtype=np.float64,
                      elements=st.floats(allow_infinity=False,
                                         allow_nan=False))


def choices(seq, size):
    strat = st.permutations(tuple(range(seq)))
    return strat.map(lambda x: tuple(seq[i] for i in x[:size]))


@st.composite
def metrics(draw) -> st.SearchStrategy[LiveMetrics]:
    num_metrics = draw(st.integers(0, 3))
    num_batch_data = draw(st.integers(0, 5))
    num_epoch_data = draw(st.integers(0, num_batch_data))

    out = defaultdict(dict)  # type: Dict[str, Dict[str, np.ndarray]]
    for name in names[:num_metrics]:
        out[name]["batch_data"] = draw(finite_array(num_batch_data))  # type: np.ndarray
        out[name]["epoch_data"] = draw(finite_array(num_epoch_data))  # type: np.ndarray
        out[name]["epoch_domain"] = np.asarray(draw(choices(np.arange(1, num_batch_data + 1),
                                                            size=num_epoch_data)))
    return out
