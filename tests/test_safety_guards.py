"""Offline test: both hard guards fire through the real code path.

These guards exist because of a 2026-05-07 incident. Guard 1 spent an unknown
period doing nothing at all: `request()` rewrites a path to `/api/managed`
before calling `_enforce_guards`, and the prefix tuple listed only `/managed`,
so `"/api/managed".startswith("/managed")` was False and every MDR call went
straight through. Nothing caught it because nothing tested it.

So this drives `request()`, not `_enforce_guards`, and not the constant. A test
that asserts `/api/managed` is in `_MDR_PATH_PREFIXES` would still pass if
`request()` stopped calling the guard at all, which is the failure that
actually happened one layer up.

No server is needed: a blocked call raises before any socket is opened.

Run:  PYTHONPATH=src python3 -m tests.test_safety_guards
"""
import asyncio
import sys

from composer_mcp.client import (
    ComposerClient,
    ComposerConfig,
    MdrEndpointBlocked,
    SelfUserMutationBlocked,
)

CFG = ComposerConfig(
    base_url="http://127.0.0.1:1",      # deliberately dead: nothing may reach it
    context_path="/discovery",
    user="nobody",
    password="nobody",
)

# Every spelling a caller might reasonably use. The bug was that the guard saw
# a different string from the one the caller wrote, so the shapes matter.
MDR_PATHS = [
    "/managed",
    "managed",
    "/managed/",
    "/managed/reports",
    "/managed/datasets/42",
    "/api/managed",
    "/api/managed/reports",
]

failures: list[str] = []


async def main() -> None:
    client = ComposerClient(CFG)
    try:
        # 1. every MDR spelling is blocked, through request()
        for path in MDR_PATHS:
            for method in ("GET", "POST", "PUT", "DELETE"):
                try:
                    await client.request(method, path)
                except MdrEndpointBlocked:
                    continue
                except Exception as exc:                     # noqa: BLE001
                    failures.append(
                        f"{method} {path}: guard did not fire, reached the transport "
                        f"instead and raised {type(exc).__name__}. An MDR call escaped."
                    )
                else:
                    failures.append(f"{method} {path}: no exception at all")

        # 2. The guard is a prefix match and is DELIBERATELY broad: `/managedfoo`
        #    is blocked too. For a block written after an incident, over-blocking
        #    is the right failure direction, and no path containing "managed"
        #    exists on 26.2.0 anyway (checked against the live api-docs), so it
        #    costs nothing today. This test asserted the opposite first and would
        #    have had someone narrow a safety guard to satisfy it.
        try:
            await client.request("GET", "/managedfoo")
        except MdrEndpointBlocked:
            pass                                              # intended
        except Exception as exc:                              # noqa: BLE001
            failures.append(f"GET /managedfoo: prefix guard has been narrowed, "
                            f"raised {type(exc).__name__} instead of blocking")

        #    It must still be selective, or it would pass by blocking everything.
        #    These reach the transport and fail to connect, which is the proof
        #    they got past the guard.
        for path in ("/sources", "/dashboards", "/api/management", "/materialized-views"):
            try:
                await client.request("GET", path)
            except MdrEndpointBlocked:
                failures.append(f"GET {path}: wrongly blocked as MDR, the guard is too broad")
            except Exception:                                # noqa: BLE001, S110
                pass                                          # expected: dead host
            else:
                failures.append(f"GET {path}: unexpectedly succeeded against a dead host")

        # 3. guard 2: refuse to mutate the running session's own user
        client._running_user_id = "me-123"                    # noqa: SLF001
        client._running_user_id_fetched = True                # noqa: SLF001
        for method in ("PUT", "PATCH", "DELETE"):
            try:
                await client.request(method, "/users/me-123")
            except SelfUserMutationBlocked:
                continue
            except Exception as exc:                          # noqa: BLE001
                failures.append(
                    f"{method} /users/me-123: self-mutation guard did not fire, "
                    f"raised {type(exc).__name__} instead"
                )
            else:
                failures.append(f"{method} /users/me-123: no exception at all")

        # and it must not block a different user
        try:
            await client.request("PUT", "/users/someone-else")
        except SelfUserMutationBlocked:
            failures.append("PUT /users/someone-else: wrongly blocked, guard is too broad")
        except Exception:                                     # noqa: BLE001, S110
            pass
    finally:
        await client.aclose()

    for f in failures:
        print(f"FAIL  {f}")
    if failures:
        sys.exit(1)
    print(f"ok: {len(MDR_PATHS) * 4} MDR calls blocked, 4 non-MDR calls passed the guard, "
          f"3 self-mutations blocked, 1 other-user mutation allowed")


if __name__ == "__main__":
    asyncio.run(main())
