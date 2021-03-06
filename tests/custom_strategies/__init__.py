import pprint
from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, Optional, Sequence, Union, Tuple, TypeVar

import hypothesis.extra.numpy as hnp
import hypothesis.strategies as st
import numpy as np
from matplotlib import colors

from noggin.plotter import LiveLogger, LivePlot
from noggin.typing import LiveMetrics, ValidColor

__all__ = [
    "finite_arrays",
    "choices",
    "metric_dict",
    "live_metrics",
    "loggers",
    "matplotlib_colors",
    "plot_kwargs",
]

T = TypeVar("T")


def draw_if_strategy(
    data: st.DataObject,
    value: Union[T, st.SearchStrategy[T]],
    label: Optional[str] = None,
) -> T:
    if isinstance(value, st.SearchStrategy):
        return data.draw(value, label=label)
    return value


a_bunch_of_colors = list(colors.BASE_COLORS.keys())
a_bunch_of_colors.extend(colors.BASE_COLORS.values())
a_bunch_of_colors.extend(colors.CSS4_COLORS.keys())
a_bunch_of_colors.extend(colors.CSS4_COLORS.values())
a_bunch_of_colors.extend(["C{}".format(i) for i in range(10)])
a_bunch_of_colors.append((1.0, 0.0, 0.0, 0.5))
a_bunch_of_colors.append(None)


def plot_kwargs() -> st.SearchStrategy[Dict[str, Any]]:
    def _filter_key_if_none(d: dict):
        return {k: v for k, v in d.items() if v is not None}

    return st.fixed_dictionaries(
        dict(
            figsize=st.none() | st.tuples(*[st.floats(min_value=1, max_value=10)] * 2),
            max_fraction_spent_plotting=st.none() | st.floats(0.0, 1.0),
            last_n_batches=st.none() | st.integers(1, 10),
            nrows=st.none() | st.integers(1, 3),
            ncols=st.none() | st.integers(1, 3),
        )
    ).map(_filter_key_if_none)


def matplotlib_colors() -> st.SearchStrategy[ValidColor]:
    return st.sampled_from(a_bunch_of_colors)


def everything_except(
    excluded_types: Union[type, Tuple[type, ...]]
) -> st.SearchStrategy[Any]:
    return (
        st.from_type(type)
        .flatmap(st.from_type)
        .filter(lambda x: not isinstance(x, excluded_types))
    )


def finite_arrays(size):
    return hnp.arrays(
        shape=(size,),
        dtype=np.float64,
        elements=st.floats(min_value=-1e6, max_value=1e6),
    )


def choices(seq: Sequence, size: int) -> st.SearchStrategy[Tuple]:
    assert size <= len(seq)
    return st.sampled_from(tuple(combinations(seq, size)))


@st.composite
def metric_dict(
    draw, name, num_batch_data=None, num_epoch_data=None, epoch_domain=None
) -> st.SearchStrategy[Dict[str, np.ndarray]]:
    if all(x is not None for x in (num_batch_data, num_epoch_data)):
        assert num_batch_data >= num_epoch_data

    if num_batch_data is None:
        num_batch_data = draw(st.integers(0, 5))

    if num_epoch_data is None:
        num_epoch_data = draw(st.integers(0, num_batch_data))

    if epoch_domain is None:
        epoch_domain = draw(
            choices(np.arange(1, num_batch_data + 1), size=num_epoch_data)
        )

    out = dict(name=name)  # type: Dict[str, np.ndarray]
    out["batch_data"] = draw(finite_arrays(num_batch_data))  # type: np.ndarray
    out["epoch_data"] = draw(finite_arrays(num_epoch_data))  # type: np.ndarray
    out["epoch_domain"] = np.asarray(sorted(epoch_domain))
    out["cnt_since_epoch"] = draw(st.integers(0, num_batch_data - num_epoch_data))
    out["total_weighting"] = (
        draw(st.floats(0.0, 10.0)) if out["cnt_since_epoch"] else 0.0
    )
    out["running_weighted_sum"] = (
        draw(st.floats(-10.0, 10.0)) if out["cnt_since_epoch"] else 0.0
    )
    return out


@st.composite
def live_metrics(draw, min_num_metrics=0) -> st.SearchStrategy[LiveMetrics]:
    num_metrics = draw(st.integers(min_num_metrics, 3))
    num_batch_data = draw(st.integers(0, 5))
    num_epoch_data = draw(st.integers(0, num_batch_data))

    out = defaultdict(dict)  # type: Dict[str, Dict[str, np.ndarray]]
    for name in ["metric_a", "metric_b", "metric_c"][:num_metrics]:
        out[name] = draw(
            metric_dict(
                name, num_batch_data=num_batch_data, num_epoch_data=num_epoch_data
            )
        )
    return dict(out.items())


def verbose_repr(self):
    metrics = sorted(set(self._train_metrics).union(set(self._test_metrics)))
    msg = "{}({})\n".format(type(self).__name__, ", ".join(metrics))

    words = ("training batches", "training epochs", "testing batches", "testing epochs")
    things = (
        self._num_train_batch,
        self._num_train_epoch,
        self._num_test_batch,
        self._num_test_epoch,
    )

    for word, thing in zip(words, things):
        msg += "number of {word} set: {thing}\n".format(word=word, thing=thing)

    msg += "train metrics:\n{}\n".format(pprint.pformat(dict(self.train_metrics)))
    msg += "test metrics:\n{}".format(pprint.pformat(dict(self.test_metrics)))
    return msg


class VerboseLogger(LiveLogger):
    def __repr__(self):
        return verbose_repr(self)


class VerbosePlotter(LivePlot):
    def __repr__(self):
        return verbose_repr(self)


@st.composite
def loggers(draw, min_num_metrics=0) -> st.SearchStrategy[LiveLogger]:
    train_metrics = draw(live_metrics(min_num_metrics=min_num_metrics))
    test_metrics = draw(live_metrics(min_num_metrics=min_num_metrics))
    return VerboseLogger.from_dict(
        dict(
            train_metrics=train_metrics,
            test_metrics=test_metrics,
            num_train_epoch=max(
                (len(v["epoch_data"]) for v in train_metrics.values()), default=0
            ),
            num_train_batch=max(
                (len(v["batch_data"]) for v in train_metrics.values()), default=0
            ),
            num_test_epoch=max(
                (len(v["epoch_data"]) for v in test_metrics.values()), default=0
            ),
            num_test_batch=max(
                (len(v["batch_data"]) for v in test_metrics.values()), default=0
            ),
        )
    )


@st.composite
def plotters(draw) -> st.SearchStrategy[LivePlot]:
    train_metrics = draw(live_metrics())
    min_num_test = 1 if not train_metrics else 0
    test_metrics = draw(live_metrics(min_num_metrics=min_num_test))
    metric_names = sorted(set(train_metrics).union(set(test_metrics)))
    train_colors = {k: draw(matplotlib_colors()) for k in train_metrics}
    test_colors = {k: draw(matplotlib_colors()) for k in test_metrics}

    return LivePlot.from_dict(
        dict(
            train_metrics=train_metrics,
            test_metrics=test_metrics,
            num_train_epoch=max(
                (len(v["epoch_data"]) for v in train_metrics.values()), default=0
            ),
            num_train_batch=max(
                (len(v["batch_data"]) for v in train_metrics.values()), default=0
            ),
            num_test_epoch=max(
                (len(v["epoch_data"]) for v in test_metrics.values()), default=0
            ),
            num_test_batch=max(
                (len(v["batch_data"]) for v in test_metrics.values()), default=0
            ),
            max_fraction_spent_plotting=draw(st.floats(0, 1)),
            last_n_batches=draw(st.none() | st.integers(1, 100)),
            pltkwargs=dict(figsize=(3, 2), nrows=len(metric_names), ncols=1),
            train_colors=train_colors,
            test_colors=test_colors,
            metric_names=metric_names,
        )
    )
