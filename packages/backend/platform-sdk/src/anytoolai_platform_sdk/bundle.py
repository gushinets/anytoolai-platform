from __future__ import annotations

import inspect
from pathlib import Path


class ProductBundle:
    """Product-neutral contract a product-platform package implements to be composed by
    apps/platform-api's bootstrap.py. platform-sdk owns this contract (not platform-core) so
    platform-core/platform-actions never need to import a product-platforms package -- only the
    application composition root does."""

    bundle_id: str = "base"

    def config_roots(self) -> list[Path]:
        """Resolved, absolute product config directories this bundle contributes, in the order
        they should be loaded. Each entry is a fully-formed product directory (containing its own
        product.yaml, action_configs.yaml, workflows.yaml, scenarios.yaml, prompts.yaml,
        schemas.yaml, frontends.yaml, and optional quotas.yaml/handoffs.yaml/analytics.yaml) --
        no further nesting is expected. A bundle with no implemented products returns []."""
        return []

    def _package_dir(self) -> Path:
        """The directory containing the concrete bundle subclass's own module file, resolved
        independently of the caller's current working directory -- mirrors
        anytoolai_platform_core.bootstrap.registry.default_config_root()'s per-repo
        `Path(__file__).resolve()` pattern, scoped per-bundle instead of per-repo. Subclasses use
        this to build package-relative config roots, e.g. `self._package_dir() / "products" /
        "proposal_ai"`."""
        try:
            module_file = inspect.getfile(type(self))
        except (TypeError, OSError) as error:
            # inspect.getfile raises TypeError for a class not backed by any source file at all
            # (a genuine builtin, or a class whose module was never registered in sys.modules),
            # and OSError for a class defined in __main__/REPL/exec with no __file__ (e.g. a
            # dynamically-built `type(...)` class run as a script or interactively). Every real
            # bundle is an ordinary subclass in an installed package, so neither is reachable in
            # production; the explicit error just replaces an opaque TypeError/OSError with a
            # message that names the actual contract being violated, in case this ever becomes a
            # public extension point for less-controlled bundle authors.
            raise TypeError(
                f"{type(self).__name__} must be defined in a real module file on disk for "
                "_package_dir() to resolve its config roots"
            ) from error
        return Path(module_file).resolve().parent
