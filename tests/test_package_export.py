"""Star-import contract: ``from poor_richard_agent import *`` must succeed,
so every name in ``__all__`` must actually exist in the package.
"""

from poor_richard_agent import *  # noqa: F403

import poor_richard_agent


def test_star_import_resolves_all_names():
    for name in poor_richard_agent.__all__:
        assert name in globals(), f"__all__ lists {name!r}, which the package does not define"
