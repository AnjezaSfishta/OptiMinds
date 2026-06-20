#!/usr/bin/env python3
import argparse
import copy
import heapq
import hashlib
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set

INF = 10**30
CAPACITY = {"S": 10, "M": 20, "L": 30}


@dataclass
class Edge:
    idx: int
    a: int
    b: int
    direction: int  # 1: a->b, 2: both ways
    travel_time: int
    length_m: int
    category: str  # M/O/C
    req: int


@dataclass
class VehicleState:
    idx: int
    vtype: str
    capacity: int
    route: List[int]
    cleaned: List[int]
    current: int
    time_used: int


@dataclass
class Problem:
    n: int
    m: int
    t_limit: int
    c: int
    depot: int
    alpha: float
    edges: List[Edge]
    vehicle_types: List[str]


def parse_problem(path: str) -> Problem:
    with open(path, "r", encoding="ascii") as f:
        raw_lines = [ln.strip() for ln in f if ln.strip()]

    first = raw_lines[0].split()
    n, m, t_limit, c, depot = map(int, first[:5])
    alpha = float(first[5])

    # Some datasets include N coordinate lines, others omit them.
    # We detect the format by token count and expected total lines.
    idx = 1
    remaining = len(raw_lines) - idx
    if remaining == m + 1:
        pass
    else:
        maybe_coords = True
        if remaining >= n + m + 1:
            for k in range(idx, idx + n):
                parts = raw_lines[k].split()
                if len(parts) != 2:
                    maybe_coords = False
                    break
            if maybe_coords:
                idx += n

    edges: List[Edge] = []
    for j in range(m):
        parts = raw_lines[idx + j].split()
        if len(parts) != 7:
            raise ValueError(f"Invalid street line at index {j}: {raw_lines[idx + j]}")
        a, b, direction, travel_time, length_m = map(int, parts[:5])
        category = parts[5]
        req = int(parts[6])
        edges.append(
            Edge(
                idx=j,
                a=a,
                b=b,
                direction=direction,
                travel_time=travel_time,
                length_m=length_m,
                category=category,
                req=req,
            )
        )

    vehicle_parts = raw_lines[idx + m].split()
    if len(vehicle_parts) != c:
        raise ValueError("Vehicle count line does not match C")

    return Problem(
        n=n,
        m=m,
        t_limit=t_limit,
        c=c,
        depot=depot,
        alpha=alpha,
        edges=edges,
        vehicle_types=vehicle_parts,
    )


def build_graph(problem: Problem) -> Tuple[List[List[Tuple[int, int]]], List[List[Tuple[int, int]]]]:
    graph = [[] for _ in range(problem.n)]
    rev = [[] for _ in range(problem.n)]
    for e in problem.edges:
        graph[e.a].append((e.b, e.travel_time))
        rev[e.b].append((e.a, e.travel_time))
        if e.direction == 2:
            graph[e.b].append((e.a, e.travel_time))
            rev[e.a].append((e.b, e.travel_time))
    return graph, rev


def dijkstra(n: int, graph: List[List[Tuple[int, int]]], src: int) -> Tuple[List[int], List[int]]:
    dist = [INF] * n
    prev = [-1] * n
    dist[src] = 0
    pq: List[Tuple[int, int]] = [(0, src)]

    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]:
            continue
        for v, w in graph[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def reconstruct_path(prev: List[int], src: int, dst: int) -> List[int]:
    if src == dst:
        return [src]
    if prev[dst] == -1:
        return []
    out = []
    cur = dst
    while cur != -1:
        out.append(cur)
        if cur == src:
            break
        cur = prev[cur]
    if out[-1] != src:
        return []
    out.reverse()
    return out


def path_to_depot(prev_to_depot: List[int], start: int, depot: int) -> List[int]:
    if start == depot:
        return [depot]
    out = [start]
    cur = start
    seen = {start}
    while cur != depot:
        nxt = prev_to_depot[cur]
        if nxt == -1 or nxt in seen:
            return []
        out.append(nxt)
        seen.add(nxt)
        cur = nxt
    return out


def cleaning_orientations(e: Edge) -> List[Tuple[int, int]]:
    if e.direction == 1:
        return [(e.a, e.b)]
    return [(e.a, e.b), (e.b, e.a)]


def min_base_trip(
    e: Edge,
    dist_from_depot: List[int],
    dist_to_depot: List[int],
) -> int:
    best = INF
    for s, t in cleaning_orientations(e):
        if dist_from_depot[s] >= INF or dist_to_depot[t] >= INF:
            continue
        cand = dist_from_depot[s] + e.travel_time + dist_to_depot[t]
        if cand < best:
            best = cand
    return best


def choose_best_edge(
    problem: Problem,
    edges: List[Edge],
    candidates: Set[int],
    capacity: int,
    current: int,
    time_used: int,
    dist_cur: List[int],
    dist_from_depot: List[int],
    dist_to_depot: List[int],
    l_max: float,
    w_max: float,
    mandatory_mode: bool,
    mandatory_hard_first: bool,
) -> Tuple[Optional[int], Optional[Tuple[int, int]]]:
    best_eid: Optional[int] = None
    best_orient: Optional[Tuple[int, int]] = None
    best_score = -INF

    for eid in candidates:
        e = edges[eid]
        if e.category == "C" or e.req > capacity:
            continue

        best_for_edge = None
        best_o = None
        best_extra = INF

        for s, t in cleaning_orientations(e):
            if dist_cur[s] >= INF or dist_to_depot[t] >= INF:
                continue
            extra = dist_cur[s] + e.travel_time
            finish_time = time_used + extra + dist_to_depot[t]
            if finish_time > problem.t_limit:
                continue
            if extra < best_extra:
                best_extra = extra
                best_o = (s, t)

        if best_o is None:
            continue

        len_gain = float(e.length_m)
        waste = float(capacity - e.req) * (float(e.length_m) / 1000.0)
        coverage_gain = len_gain / l_max if l_max > 0 else 0.0
        waste_penalty = waste / w_max if w_max > 0 else 0.0

        if mandatory_mode:
            # Strongly prefer the smallest sufficient vehicle on mandatory streets.
            cap_gap = max(0, capacity - e.req)
            # For high-alpha instances, over-penalizing waste can hurt coverage.
            waste_pref = 5000.0 * float(cap_gap) * (1.0 - problem.alpha)
            exact_bonus = 100.0 if capacity == e.req else 0.0
            if mandatory_hard_first:
                # Prioritize hard mandatory streets first, then prefer lower detour from current position.
                base_trip = min_base_trip(e, dist_from_depot, dist_to_depot)
                best_for_edge = float(base_trip) - float(best_extra) + exact_bonus - waste_pref
            else:
                # Prefer the closest feasible next mandatory street from current position.
                best_for_edge = 1000.0 - float(best_extra) + exact_bonus - waste_pref
        else:
            objective_gain = problem.alpha * coverage_gain - (1.0 - problem.alpha) * waste_penalty
            if objective_gain <= 0.0:
                continue
            # Coverage-heavy instances should prefer absolute objective gain, not only gain/time.
            if problem.alpha >= 0.7:
                best_for_edge = objective_gain
            else:
                best_for_edge = objective_gain / max(1.0, float(best_extra))

        if best_for_edge > best_score:
            best_score = best_for_edge
            best_eid = eid
            best_orient = best_o

    return best_eid, best_orient


def append_path(route: List[int], path: List[int]) -> None:
    if not path:
        return
    if not route:
        route.extend(path)
        return
    route.extend(path[1:])


def build_edge_time_lookup(edges: List[Edge]) -> Dict[Tuple[int, int], int]:
    lookup: Dict[Tuple[int, int], int] = {}
    for e in edges:
        lookup[(e.a, e.b)] = e.travel_time
        if e.direction == 2:
            lookup[(e.b, e.a)] = e.travel_time
    return lookup


def build_edge_id_lookup(edges: List[Edge]) -> Dict[Tuple[int, int], int]:
    lookup: Dict[Tuple[int, int], int] = {}
    for e in edges:
        lookup[(e.a, e.b)] = e.idx
        if e.direction == 2:
            lookup[(e.b, e.a)] = e.idx
    return lookup


def traversed_edge_ids(route: List[int], edge_id_lookup: Dict[Tuple[int, int], int]) -> Set[int]:
    out: Set[int] = set()
    for u, v in zip(route, route[1:]):
        eid = edge_id_lookup.get((u, v))
        if eid is not None:
            out.add(eid)
    return out


def sanitize_cleaned_lists(problem: Problem, vehicles: List[VehicleState], edge_id_lookup: Dict[Tuple[int, int], int]) -> None:
    for v in vehicles:
        traversed = traversed_edge_ids(v.route, edge_id_lookup)
        kept: List[int] = []
        seen: Set[int] = set()
        for eid in v.cleaned:
            if eid in seen:
                continue
            if eid not in traversed:
                continue
            e = problem.edges[eid]
            if e.category == "C" or v.capacity < e.req:
                continue
            seen.add(eid)
            kept.append(eid)
        v.cleaned = kept


def force_cover_remaining_mandatory(
    problem: Problem,
    graph: List[List[Tuple[int, int]]],
    vehicles: List[VehicleState],
    edges: List[Edge],
    mandatory_left: Set[int],
    edge_time_lookup: Dict[Tuple[int, int], int],
    edge_id_lookup: Dict[Tuple[int, int], int],
) -> None:
    if not mandatory_left:
        return

    dijkstra_cache: Dict[int, Tuple[List[int], List[int]]] = {}

    def get_shortest_from(src: int) -> Tuple[List[int], List[int]]:
        if src not in dijkstra_cache:
            dijkstra_cache[src] = dijkstra(problem.n, graph, src)
        return dijkstra_cache[src]

    while mandatory_left:
        progressed = False
        mandatory_cover_count: Dict[int, int] = {}
        for v in vehicles:
            for x in set(v.cleaned):
                if edges[x].category == "M":
                    mandatory_cover_count[x] = mandatory_cover_count.get(x, 0) + 1

        ordered = sorted(
            mandatory_left,
            key=lambda eid: (-edges[eid].req, -edges[eid].length_m, edges[eid].travel_time),
        )

        for eid in ordered:
            if eid not in mandatory_left:
                continue

            e = edges[eid]
            best = None

            for vi, veh in enumerate(vehicles):
                if veh.capacity < e.req or len(veh.route) < 2:
                    continue

                veh_cleaned_set = set(veh.cleaned)

                # Prefix travel-time over current route, used to evaluate segment replacement quickly.
                prefix = [0]
                valid_route = True
                for a, b in zip(veh.route, veh.route[1:]):
                    tt = edge_time_lookup.get((a, b))
                    if tt is None:
                        valid_route = False
                        break
                    prefix.append(prefix[-1] + tt)
                if not valid_route:
                    continue

                for i, u in enumerate(veh.route[:-1]):
                    dist_u, prev_u = get_shortest_from(u)

                    for s, t in cleaning_orientations(e):
                        if dist_u[s] >= INF:
                            continue

                        dist_t, prev_t = get_shortest_from(t)

                        for j in range(i + 1, len(veh.route)):
                            vj = veh.route[j]
                            if dist_t[vj] >= INF:
                                continue

                            # Do not remove mandatory streets that are uniquely covered.
                            blocked = False
                            for a, b in zip(veh.route[i:j], veh.route[i + 1 : j + 1]):
                                rid = edge_id_lookup.get((a, b))
                                if rid is None:
                                    continue
                                if edges[rid].category == "M" and rid in veh_cleaned_set:
                                    if mandatory_cover_count.get(rid, 0) <= 1:
                                        blocked = True
                                        break
                            if blocked:
                                continue

                            original_segment = prefix[j] - prefix[i]
                            inserted_segment = dist_u[s] + e.travel_time + dist_t[vj]
                            delta = inserted_segment - original_segment
                            new_time_used = veh.time_used + delta
                            if new_time_used > problem.t_limit:
                                continue

                            cand = (delta, new_time_used, vi, i, j, s, t, prev_u, prev_t)
                            if best is None or cand < best:
                                best = cand

            if best is None:
                continue

            _, new_time_used, vi, i, j, s, t, prev_u, prev_t = best
            veh = vehicles[vi]
            path_u_s = reconstruct_path(prev_u, veh.route[i], s)
            path_t_v = reconstruct_path(prev_t, t, veh.route[j])
            if not path_u_s or not path_t_v:
                continue

            new_route = list(veh.route[: i + 1])
            append_path(new_route, path_u_s)
            new_route.append(t)
            append_path(new_route, path_t_v)
            new_route.extend(veh.route[j + 1 :])

            veh.route = new_route
            veh.time_used = int(new_time_used)
            veh.current = new_route[-1]
            veh.cleaned.append(eid)

            sanitize_cleaned_lists(problem, vehicles, edge_id_lookup)
            all_cleaned = {x for v in vehicles for x in v.cleaned}
            mandatory_left.clear()
            mandatory_left.update(e.idx for e in edges if e.category == "M" and e.idx not in all_cleaned)

            progressed = True
            break

        if not progressed:
            break


def lookahead_mandatory_repair(
    problem: Problem,
    graph: List[List[Tuple[int, int]]],
    vehicles: List[VehicleState],
    edges: List[Edge],
    edge_time_lookup: Dict[Tuple[int, int], int],
    edge_id_lookup: Dict[Tuple[int, int], int],
    dist_from_depot: List[int],
    prev_from_depot: List[int],
    dist_to_depot: List[int],
    prev_to_depot: List[int],
) -> List[VehicleState]:
    mandatory_all = {e.idx for e in edges if e.category == "M"}

    def cleaned_ids(vs: List[VehicleState]) -> Set[int]:
        return {eid for v in vs for eid in v.cleaned}

    current_missing = mandatory_all - cleaned_ids(vehicles)
    if not current_missing:
        return vehicles

    # Keep this bounded to avoid very high runtime on large missing sets.
    missing_targets = sorted(
        list(current_missing),
        key=lambda eid: (-edges[eid].req, -edges[eid].length_m, edges[eid].travel_time),
    )[:6]

    best_solution: Optional[List[VehicleState]] = None
    best_missing_count = len(current_missing)

    dcache: Dict[int, Tuple[List[int], List[int]]] = {}

    def getd(src: int) -> Tuple[List[int], List[int]]:
        if src not in dcache:
            dcache[src] = dijkstra(problem.n, graph, src)
        return dcache[src]

    for target in missing_targets:
        e = edges[target]

        for vi, veh in enumerate(vehicles):
            if veh.capacity < e.req or len(veh.route) < 2:
                continue

            prefix = [0]
            valid_route = True
            for a, b in zip(veh.route, veh.route[1:]):
                tt = edge_time_lookup.get((a, b))
                if tt is None:
                    valid_route = False
                    break
                prefix.append(prefix[-1] + tt)
            if not valid_route:
                continue

            for i, u in enumerate(veh.route[:-1]):
                dist_u, prev_u = getd(u)
                for s, t in cleaning_orientations(e):
                    if dist_u[s] >= INF:
                        continue
                    dist_t, prev_t = getd(t)
                    for j in range(i + 1, len(veh.route)):
                        vj = veh.route[j]
                        if dist_t[vj] >= INF:
                            continue

                        old_seg = prefix[j] - prefix[i]
                        new_seg = dist_u[s] + e.travel_time + dist_t[vj]
                        delta = new_seg - old_seg
                        if veh.time_used + delta > problem.t_limit:
                            continue

                        trial = copy.deepcopy(vehicles)
                        tv = trial[vi]
                        p1 = reconstruct_path(prev_u, tv.route[i], s)
                        p2 = reconstruct_path(prev_t, t, tv.route[j])
                        if not p1 or not p2:
                            continue

                        nr = list(tv.route[: i + 1])
                        append_path(nr, p1)
                        nr.append(t)
                        append_path(nr, p2)
                        nr.extend(tv.route[j + 1 :])

                        tv.route = nr
                        tv.time_used = tv.time_used + delta
                        tv.current = nr[-1]
                        tv.cleaned.append(target)

                        sanitize_cleaned_lists(problem, trial, edge_id_lookup)

                        rem = mandatory_all - cleaned_ids(trial)
                        if rem:
                            repair_remaining_mandatory(
                                problem=problem,
                                vehicles=trial,
                                edges=edges,
                                mandatory_left=rem,
                                dist_from_depot=dist_from_depot,
                                prev_from_depot=prev_from_depot,
                                dist_to_depot=dist_to_depot,
                                prev_to_depot=prev_to_depot,
                            )
                            sanitize_cleaned_lists(problem, trial, edge_id_lookup)
                            rem = mandatory_all - cleaned_ids(trial)

                        if rem:
                            rem2 = set(rem)
                            force_cover_remaining_mandatory(
                                problem=problem,
                                graph=graph,
                                vehicles=trial,
                                edges=edges,
                                mandatory_left=rem2,
                                edge_time_lookup=edge_time_lookup,
                                edge_id_lookup=edge_id_lookup,
                            )
                            sanitize_cleaned_lists(problem, trial, edge_id_lookup)
                            rem = mandatory_all - cleaned_ids(trial)

                        if len(rem) < best_missing_count:
                            best_missing_count = len(rem)
                            best_solution = trial
                            if best_missing_count == 0:
                                return best_solution

    return best_solution if best_solution is not None else vehicles


def enrich_traversed_optional_cleaning(
    problem: Problem,
    vehicles: List[VehicleState],
    edge_id_lookup: Dict[Tuple[int, int], int],
    already_cleaned: Set[int],
    l_max: float,
    w_max: float,
) -> None:
    for v in vehicles:
        traversed_optional: Set[int] = set()
        for u, w in zip(v.route, v.route[1:]):
            eid = edge_id_lookup.get((u, w))
            if eid is None:
                continue
            e = problem.edges[eid]
            if e.category != "O":
                continue
            traversed_optional.add(eid)

        for eid in sorted(traversed_optional):
            if eid in already_cleaned:
                continue
            e = problem.edges[eid]
            if v.capacity < e.req:
                continue

            coverage_gain = (float(e.length_m) / l_max) if l_max > 0 else 0.0
            waste = float(v.capacity - e.req) * (float(e.length_m) / 1000.0)
            waste_penalty = (waste / w_max) if w_max > 0 else 0.0
            objective_gain = problem.alpha * coverage_gain - (1.0 - problem.alpha) * waste_penalty
            if objective_gain <= 0.0:
                continue

            v.cleaned.append(eid)
            already_cleaned.add(eid)


def extend_vehicle(
    problem: Problem,
    graph: List[List[Tuple[int, int]]],
    edges: List[Edge],
    vehicle: VehicleState,
    target_set: Set[int],
    dist_from_depot: List[int],
    dist_to_depot: List[int],
    prev_to_depot: List[int],
    l_max: float,
    w_max: float,
    mandatory_mode: bool,
    mandatory_hard_first: bool,
    close_route: bool = True,
) -> None:
    while target_set:
        dist_cur, prev_cur = dijkstra(problem.n, graph, vehicle.current)
        eid, orient = choose_best_edge(
            problem=problem,
            edges=edges,
            candidates=target_set,
            capacity=vehicle.capacity,
            current=vehicle.current,
            time_used=vehicle.time_used,
            dist_cur=dist_cur,
            dist_from_depot=dist_from_depot,
            dist_to_depot=dist_to_depot,
            l_max=l_max,
            w_max=w_max,
            mandatory_mode=mandatory_mode,
            mandatory_hard_first=mandatory_hard_first,
        )
        if eid is None or orient is None:
            break

        start, end = orient
        e = edges[eid]

        to_start = reconstruct_path(prev_cur, vehicle.current, start)
        if not to_start:
            # Keep this target for other vehicles or later repair.
            continue

        append_path(vehicle.route, to_start)
        vehicle.route.append(end)
        vehicle.time_used += dist_cur[start] + e.travel_time
        vehicle.current = end
        vehicle.cleaned.append(eid)
        target_set.discard(eid)

        # Keep route valid for eventual return.
        if vehicle.time_used + dist_to_depot[vehicle.current] > problem.t_limit:
            # Should not happen due to feasibility check, but guard anyway.
            break

    if close_route:
        back = path_to_depot(prev_to_depot, vehicle.current, problem.depot)
        if back and len(back) > 1:
            append_path(vehicle.route, back)
            vehicle.time_used += dist_to_depot[vehicle.current]
            vehicle.current = problem.depot


def repair_remaining_mandatory(
    problem: Problem,
    vehicles: List[VehicleState],
    edges: List[Edge],
    mandatory_left: Set[int],
    dist_from_depot: List[int],
    prev_from_depot: List[int],
    dist_to_depot: List[int],
    prev_to_depot: List[int],
) -> None:
    if not mandatory_left:
        return

    ordered = sorted(
        mandatory_left,
        key=lambda eid: (-edges[eid].req, -edges[eid].length_m, edges[eid].travel_time),
    )

    for eid in ordered:
        if eid not in mandatory_left:
            continue

        e = edges[eid]
        best: Optional[Tuple[int, Tuple[int, int], int, float]] = None

        for vi, v in enumerate(vehicles):
            if v.capacity < e.req:
                continue

            remaining = problem.t_limit - v.time_used
            if remaining <= 0:
                continue

            for s, t in cleaning_orientations(e):
                if dist_from_depot[s] >= INF or dist_to_depot[t] >= INF:
                    continue

                trip_time = dist_from_depot[s] + e.travel_time + dist_to_depot[t]
                if trip_time > remaining:
                    continue

                waste = float(v.capacity - e.req) * (float(e.length_m) / 1000.0)
                cand = (vi, (s, t), trip_time, waste)

                if best is None:
                    best = cand
                else:
                    _, _, best_trip, best_waste = best
                    if trip_time < best_trip or (trip_time == best_trip and waste < best_waste):
                        best = cand

        if best is None:
            continue

        vi, (s, t), trip_time, _ = best
        v = vehicles[vi]

        # Ensure route currently closes at depot before appending a forced trip.
        if v.current != problem.depot:
            back = path_to_depot(prev_to_depot, v.current, problem.depot)
            if back and len(back) > 1:
                append_path(v.route, back)
                v.time_used += dist_to_depot[v.current]
                v.current = problem.depot

        to_start = reconstruct_path(prev_from_depot, problem.depot, s)
        back = path_to_depot(prev_to_depot, t, problem.depot)
        if not to_start or not back:
            continue

        append_path(v.route, to_start)
        v.route.append(t)
        append_path(v.route, back)

        v.time_used += trip_time
        v.current = problem.depot
        v.cleaned.append(eid)
        mandatory_left.discard(eid)


def build_empty_vehicles(problem: Problem) -> List[VehicleState]:
    out: List[VehicleState] = []
    for i, vt in enumerate(problem.vehicle_types):
        out.append(
            VehicleState(
                idx=i,
                vtype=vt,
                capacity=CAPACITY[vt],
                route=[problem.depot],
                cleaned=[],
                current=problem.depot,
                time_used=0,
            )
        )
    return out


def mandatory_only_fallback(
    problem: Problem,
    edges: List[Edge],
    mandatory_ids: Set[int],
    dist_from_depot: List[int],
    prev_from_depot: List[int],
    dist_to_depot: List[int],
    prev_to_depot: List[int],
) -> Optional[List[VehicleState]]:
    vehicles = build_empty_vehicles(problem)
    remaining = set(mandatory_ids)

    ordered = sorted(
        remaining,
        key=lambda eid: (-edges[eid].req, -edges[eid].length_m, edges[eid].travel_time),
    )

    for eid in ordered:
        e = edges[eid]
        best: Optional[Tuple[int, Tuple[int, int], int, float]] = None

        for vi, v in enumerate(vehicles):
            if v.capacity < e.req:
                continue
            rem_time = problem.t_limit - v.time_used
            if rem_time <= 0:
                continue

            for s, t in cleaning_orientations(e):
                if dist_from_depot[s] >= INF or dist_to_depot[t] >= INF:
                    continue
                trip_time = dist_from_depot[s] + e.travel_time + dist_to_depot[t]
                if trip_time > rem_time:
                    continue
                waste = float(v.capacity - e.req) * (float(e.length_m) / 1000.0)
                cand = (vi, (s, t), trip_time, waste)
                if best is None:
                    best = cand
                else:
                    _, _, best_trip, best_waste = best
                    if trip_time < best_trip or (trip_time == best_trip and waste < best_waste):
                        best = cand

        if best is None:
            return None

        vi, (s, t), trip_time, _ = best
        v = vehicles[vi]
        to_start = reconstruct_path(prev_from_depot, problem.depot, s)
        back = path_to_depot(prev_to_depot, t, problem.depot)
        if not to_start or not back:
            return None

        append_path(v.route, to_start)
        v.route.append(t)
        append_path(v.route, back)
        v.time_used += trip_time
        v.current = problem.depot
        v.cleaned.append(eid)

    return vehicles


def preassign_critical_mandatory(
    problem: Problem,
    vehicles: List[VehicleState],
    edges: List[Edge],
    mandatory_20: Set[int],
    mandatory_30: Set[int],
    dist_from_depot: List[int],
    prev_from_depot: List[int],
    dist_to_depot: List[int],
    prev_to_depot: List[int],
) -> None:
    # Reserve time early for long mandatory streets that are easy to miss later.
    critical: List[Tuple[int, int, Tuple[int, int]]] = []
    threshold = int(0.4 * problem.t_limit)

    for eid in sorted(set(mandatory_20) | set(mandatory_30)):
        e = edges[eid]
        best_trip = INF
        best_orient: Optional[Tuple[int, int]] = None
        for s, t in cleaning_orientations(e):
            if dist_from_depot[s] >= INF or dist_to_depot[t] >= INF:
                continue
            trip = dist_from_depot[s] + e.travel_time + dist_to_depot[t]
            if trip < best_trip:
                best_trip = trip
                best_orient = (s, t)
        if best_orient is not None and best_trip >= threshold:
            critical.append((best_trip, eid, best_orient))

    # Longer trips first, to reduce the risk they become infeasible later.
    critical.sort(reverse=True)

    for trip, eid, (s, t) in critical:
        e = edges[eid]
        candidates: List[Tuple[int, int, int]] = []
        for vi, v in enumerate(vehicles):
            if v.capacity < e.req:
                continue
            rem = problem.t_limit - v.time_used
            if trip <= rem:
                # Prefer smallest sufficient capacity, then larger remaining slack.
                candidates.append((v.capacity, -rem, vi))
        if not candidates:
            continue

        candidates.sort()
        _, _, vi = candidates[0]
        v = vehicles[vi]
        to_start = reconstruct_path(prev_from_depot, problem.depot, s)
        back = path_to_depot(prev_to_depot, t, problem.depot)
        if not to_start or not back:
            continue

        if v.current != problem.depot:
            v.current = problem.depot

        append_path(v.route, to_start)
        v.route.append(t)
        append_path(v.route, back)
        v.time_used += trip
        v.current = problem.depot
        v.cleaned.append(eid)

        mandatory_20.discard(eid)
        mandatory_30.discard(eid)


def optional_roundtrip_cleanup(
    problem: Problem,
    vehicles: List[VehicleState],
    edges: List[Edge],
    optional_left: Set[int],
    dist_from_depot: List[int],
    prev_from_depot: List[int],
    dist_to_depot: List[int],
    prev_to_depot: List[int],
    l_max: float,
    w_max: float,
) -> None:
    if not optional_left:
        return

    # Consume remaining per-vehicle slack with independent depot round-trips.
    while True:
        progressed = False
        order = sorted(
            range(problem.c),
            key=lambda vi: (problem.t_limit - vehicles[vi].time_used, vehicles[vi].capacity),
            reverse=True,
        )

        for vi in order:
            v = vehicles[vi]
            remaining = problem.t_limit - v.time_used
            if remaining <= 0:
                continue

            # Keep each round-trip independent from depot.
            if v.current != problem.depot:
                back = path_to_depot(prev_to_depot, v.current, problem.depot)
                if back and len(back) > 1 and v.time_used + dist_to_depot[v.current] <= problem.t_limit:
                    append_path(v.route, back)
                    v.time_used += dist_to_depot[v.current]
                v.current = problem.depot

            best = None
            for eid in list(optional_left):
                e = edges[eid]
                if e.category != "O" or e.req > v.capacity:
                    continue

                best_trip = INF
                best_orient = None
                for s, t in cleaning_orientations(e):
                    if dist_from_depot[s] >= INF or dist_to_depot[t] >= INF:
                        continue
                    trip = dist_from_depot[s] + e.travel_time + dist_to_depot[t]
                    if trip < best_trip:
                        best_trip = trip
                        best_orient = (s, t)

                if best_orient is None or best_trip > remaining:
                    continue

                coverage_gain = (float(e.length_m) / l_max) if l_max > 0 else 0.0
                waste = float(v.capacity - e.req) * (float(e.length_m) / 1000.0)
                waste_penalty = (waste / w_max) if w_max > 0 else 0.0
                value = problem.alpha * coverage_gain - (1.0 - problem.alpha) * waste_penalty
                if value <= 0.0:
                    continue
                score = value / max(1.0, float(best_trip))

                key = (score, coverage_gain, -waste_penalty, -float(best_trip))
                if best is None or key > best[0]:
                    best = (key, eid, best_orient, best_trip)

            if best is None:
                continue

            _, eid, (s, t), trip = best
            to_start = reconstruct_path(prev_from_depot, problem.depot, s)
            back = path_to_depot(prev_to_depot, t, problem.depot)
            if not to_start or not back:
                optional_left.discard(eid)
                continue

            append_path(v.route, to_start)
            v.route.append(t)
            append_path(v.route, back)
            v.time_used += trip
            v.current = problem.depot
            v.cleaned.append(eid)
            optional_left.discard(eid)
            progressed = True

        if not progressed:
            break


def count_missing_mandatory(vehicles: List[VehicleState], mandatory_ids: Set[int]) -> int:
    cleaned = {eid for v in vehicles for eid in v.cleaned}
    return len(mandatory_ids - cleaned)


def plan_mandatory_variation(
    problem: Problem,
    graph: List[List[Tuple[int, int]]],
    dist_from_depot: List[int],
    prev_from_depot: List[int],
    dist_to_depot: List[int],
    prev_to_depot: List[int],
    l_max: float,
    w_max: float,
    order_30: List[int],
    order_20: List[int],
    order_10: List[int],
    hard_30: bool,
    hard_20: bool,
    hard_10: bool,
) -> Tuple[List[VehicleState], Set[int]]:
    vehicles = build_empty_vehicles(problem)

    mandatory_10 = {e.idx for e in problem.edges if e.category == "M" and e.req == 10}
    mandatory_20 = {e.idx for e in problem.edges if e.category == "M" and e.req == 20}
    mandatory_30 = {e.idx for e in problem.edges if e.category == "M" and e.req == 30}

    # Critical preassignment was too aggressive on some instances and could
    # reduce total mandatory coverage; keep mandatory planning adaptive.

    for vi in order_30:
        extend_vehicle(
            problem=problem,
            graph=graph,
            edges=problem.edges,
            vehicle=vehicles[vi],
            target_set=mandatory_30,
            dist_from_depot=dist_from_depot,
            dist_to_depot=dist_to_depot,
            prev_to_depot=prev_to_depot,
            l_max=l_max,
            w_max=w_max,
            mandatory_mode=True,
            mandatory_hard_first=hard_30,
        )
    repair_remaining_mandatory(
        problem=problem,
        vehicles=vehicles,
        edges=problem.edges,
        mandatory_left=mandatory_30,
        dist_from_depot=dist_from_depot,
        prev_from_depot=prev_from_depot,
        dist_to_depot=dist_to_depot,
        prev_to_depot=prev_to_depot,
    )

    for vi in order_20:
        extend_vehicle(
            problem=problem,
            graph=graph,
            edges=problem.edges,
            vehicle=vehicles[vi],
            target_set=mandatory_20,
            dist_from_depot=dist_from_depot,
            dist_to_depot=dist_to_depot,
            prev_to_depot=prev_to_depot,
            l_max=l_max,
            w_max=w_max,
            mandatory_mode=True,
            mandatory_hard_first=hard_20,
        )
    repair_remaining_mandatory(
        problem=problem,
        vehicles=vehicles,
        edges=problem.edges,
        mandatory_left=mandatory_20,
        dist_from_depot=dist_from_depot,
        prev_from_depot=prev_from_depot,
        dist_to_depot=dist_to_depot,
        prev_to_depot=prev_to_depot,
    )

    for vi in order_10:
        extend_vehicle(
            problem=problem,
            graph=graph,
            edges=problem.edges,
            vehicle=vehicles[vi],
            target_set=mandatory_10,
            dist_from_depot=dist_from_depot,
            dist_to_depot=dist_to_depot,
            prev_to_depot=prev_to_depot,
            l_max=l_max,
            w_max=w_max,
            mandatory_mode=True,
            mandatory_hard_first=hard_10,
        )
    repair_remaining_mandatory(
        problem=problem,
        vehicles=vehicles,
        edges=problem.edges,
        mandatory_left=mandatory_10,
        dist_from_depot=dist_from_depot,
        prev_from_depot=prev_from_depot,
        dist_to_depot=dist_to_depot,
        prev_to_depot=prev_to_depot,
    )

    remaining = set().union(mandatory_10, mandatory_20, mandatory_30)
    return vehicles, remaining


def solve(problem: Problem) -> List[VehicleState]:
    graph, rev_graph = build_graph(problem)

    dist_from_depot, prev_from_depot = dijkstra(problem.n, graph, problem.depot)
    dist_to_depot, prev_to_depot = dijkstra(problem.n, rev_graph, problem.depot)
    edge_time_lookup = build_edge_time_lookup(problem.edges)
    edge_id_lookup = build_edge_id_lookup(problem.edges)

    mandatory: Set[int] = set()
    optional: Set[int] = set()
    l_max = 0.0
    w_max = 0.0

    for e in problem.edges:
        if e.category in ("M", "O"):
            l_max += float(e.length_m)
            w_max += float(30 - e.req) * (float(e.length_m) / 1000.0)
        if e.category == "M":
            mandatory.add(e.idx)
        elif e.category == "O":
            optional.add(e.idx)

    mandatory_all = set(mandatory)

    template_vehicles = build_empty_vehicles(problem)
    by_cap_asc = sorted(range(problem.c), key=lambda i: template_vehicles[i].capacity)
    by_cap_desc = list(reversed(by_cap_asc))
    l_only_asc = [i for i in by_cap_asc if template_vehicles[i].capacity == 30]
    l_only_desc = list(reversed(l_only_asc))
    m_then_l_asc = [i for i in by_cap_asc if template_vehicles[i].capacity >= 20]
    m_then_l_desc = list(reversed(m_then_l_asc))

    variants = [
        (l_only_asc, m_then_l_asc, by_cap_asc),
        (l_only_desc, m_then_l_asc, by_cap_asc),
        (l_only_asc, m_then_l_desc, by_cap_asc),
        (l_only_desc, m_then_l_desc, by_cap_asc),
        (l_only_asc, m_then_l_asc, by_cap_desc),
        (l_only_desc, m_then_l_asc, by_cap_desc),
        (l_only_asc, m_then_l_desc, by_cap_desc),
        (l_only_desc, m_then_l_desc, by_cap_desc),
    ]
    policy_variants = [
        (True, True, True),
        (True, True, False),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ]

    # Add deterministic randomized variants for better generalization on unseen instances.
    rng = random.Random((problem.n << 20) ^ (problem.m << 8) ^ (problem.c << 2) ^ int(problem.alpha * 1000))
    random_variants: List[Tuple[List[int], List[int], List[int], Tuple[bool, bool, bool]]] = []
    for _ in range(80):
        o30 = l_only_asc[:]
        o20 = m_then_l_asc[:]
        o10 = by_cap_asc[:] if rng.random() < 0.5 else by_cap_desc[:]
        rng.shuffle(o30)
        rng.shuffle(o20)
        rng.shuffle(o10)
        hard = (rng.random() < 0.7, rng.random() < 0.7, rng.random() < 0.5)
        random_variants.append((o30, o20, o10, hard))

    best_vehicles: Optional[List[VehicleState]] = None
    best_remaining: Optional[Set[int]] = None
    best_missing = INF

    solved = False
    for order_30, order_20, order_10 in variants:
        for hard_30, hard_20, hard_10 in policy_variants:
            candidate_vehicles, candidate_remaining = plan_mandatory_variation(
                problem=problem,
                graph=graph,
                dist_from_depot=dist_from_depot,
                prev_from_depot=prev_from_depot,
                dist_to_depot=dist_to_depot,
                prev_to_depot=prev_to_depot,
                l_max=l_max,
                w_max=w_max,
                order_30=order_30,
                order_20=order_20,
                order_10=order_10,
                hard_30=hard_30,
                hard_20=hard_20,
                hard_10=hard_10,
            )
            missing = len(candidate_remaining)
            if missing < best_missing:
                best_missing = missing
                best_vehicles = candidate_vehicles
                best_remaining = candidate_remaining
            if missing == 0:
                solved = True
                break
        if solved:
            break

    if not solved:
        for order_30, order_20, order_10, (hard_30, hard_20, hard_10) in random_variants:
            candidate_vehicles, candidate_remaining = plan_mandatory_variation(
                problem=problem,
                graph=graph,
                dist_from_depot=dist_from_depot,
                prev_from_depot=prev_from_depot,
                dist_to_depot=dist_to_depot,
                prev_to_depot=prev_to_depot,
                l_max=l_max,
                w_max=w_max,
                order_30=order_30,
                order_20=order_20,
                order_10=order_10,
                hard_30=hard_30,
                hard_20=hard_20,
                hard_10=hard_10,
            )
            missing = len(candidate_remaining)
            if missing < best_missing:
                best_missing = missing
                best_vehicles = candidate_vehicles
                best_remaining = candidate_remaining
            if missing == 0:
                solved = True
                break

    vehicles = best_vehicles if best_vehicles is not None else build_empty_vehicles(problem)
    mandatory = best_remaining if best_remaining is not None else set(mandatory_all)

    # If mandatory streets still remain, rebuild from scratch with a mandatory-only fallback.
    if mandatory:
        fallback = mandatory_only_fallback(
            problem=problem,
            edges=problem.edges,
            mandatory_ids=mandatory_all,
            dist_from_depot=dist_from_depot,
            prev_from_depot=prev_from_depot,
            dist_to_depot=dist_to_depot,
            prev_to_depot=prev_to_depot,
        )
        if fallback is not None:
            vehicles = fallback
            mandatory.clear()

    if mandatory:
        force_cover_remaining_mandatory(
            problem=problem,
            graph=graph,
            vehicles=vehicles,
            edges=problem.edges,
            mandatory_left=mandatory,
            edge_time_lookup=edge_time_lookup,
            edge_id_lookup=edge_id_lookup,
        )
        sanitize_cleaned_lists(problem, vehicles, edge_id_lookup)

    # One-step lookahead repair can resolve hard leftover mandatory edges.
    cleaned_now = {eid for v in vehicles for eid in v.cleaned}
    if mandatory_all - cleaned_now:
        vehicles = lookahead_mandatory_repair(
            problem=problem,
            graph=graph,
            vehicles=vehicles,
            edges=problem.edges,
            edge_time_lookup=edge_time_lookup,
            edge_id_lookup=edge_id_lookup,
            dist_from_depot=dist_from_depot,
            prev_from_depot=prev_from_depot,
            dist_to_depot=dist_to_depot,
            prev_to_depot=prev_to_depot,
        )

    # Optional pass: low-cap vehicles first to reduce waste.
    if problem.alpha > 0.05:
        # Free gain: clean traversed optional streets if objective gain is positive.
        precleaned = {eid for v in vehicles for eid in v.cleaned}
        enrich_traversed_optional_cleaning(
            problem=problem,
            vehicles=vehicles,
            edge_id_lookup=edge_id_lookup,
            already_cleaned=precleaned,
            l_max=l_max,
            w_max=w_max,
        )
        optional.difference_update(precleaned)

        for vi in by_cap_asc:
            extend_vehicle(
                problem=problem,
                graph=graph,
                edges=problem.edges,
                vehicle=vehicles[vi],
                target_set=optional,
                dist_from_depot=dist_from_depot,
                dist_to_depot=dist_to_depot,
                prev_to_depot=prev_to_depot,
                l_max=l_max,
                w_max=w_max,
                mandatory_mode=False,
                mandatory_hard_first=False,
            )

        # High-alpha instances benefit from spending leftover slack on extra depot round-trips.
        if problem.alpha >= 0.7 and optional:
            optional_roundtrip_cleanup(
                problem=problem,
                vehicles=vehicles,
                edges=problem.edges,
                optional_left=optional,
                dist_from_depot=dist_from_depot,
                prev_from_depot=prev_from_depot,
                dist_to_depot=dist_to_depot,
                prev_to_depot=prev_to_depot,
                l_max=l_max,
                w_max=w_max,
            )

        # Run traversed-edge enrichment once more after optional routing.
        postcleaned = {eid for v in vehicles for eid in v.cleaned}
        enrich_traversed_optional_cleaning(
            problem=problem,
            vehicles=vehicles,
            edge_id_lookup=edge_id_lookup,
            already_cleaned=postcleaned,
            l_max=l_max,
            w_max=w_max,
        )

    # Ensure every route is closed at depot.
    for v in vehicles:
        if v.current != problem.depot:
            back = path_to_depot(prev_to_depot, v.current, problem.depot)
            if back and len(back) > 1:
                append_path(v.route, back)
                v.time_used += dist_to_depot[v.current]
                v.current = problem.depot

    return vehicles


def write_submission(path: str, problem: Problem, vehicles: List[VehicleState]) -> None:
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(f"{problem.c}\n")
        for v in vehicles:
            # If a vehicle did nothing, a single depot node is the safest minimal valid route.
            if not v.route:
                v.route = [problem.depot]
            if v.route[0] != problem.depot:
                v.route.insert(0, problem.depot)
            if v.route[-1] != problem.depot:
                v.route.append(problem.depot)

            # Platform validator expects this value as traversed edge count, i.e. node_count - 1.
            f.write(f"{max(0, len(v.route) - 1)}\n")
            f.write(" ".join(str(x) for x in v.route) + "\n")
            if v.cleaned:
                f.write(" ".join(str(x) for x in v.cleaned) + "\n")
            else:
                f.write("\n")


def validate_submission_file(path: str) -> None:
    with open(path, "r", encoding="ascii") as f:
        lines = f.read().splitlines()

    if not lines:
        raise ValueError("Submission file is empty")

    c = int(lines[0].strip())
    i = 1
    for vehicle_index in range(c):
        if i >= len(lines):
            raise ValueError(f"Missing route length line for vehicle {vehicle_index}")

        n = int(lines[i].strip())
        i += 1

        if i >= len(lines):
            raise ValueError(f"Missing route node line for vehicle {vehicle_index}")

        route_tokens = [tok for tok in lines[i].split(" ") if tok]
        i += 1

        # Platform parser expects n = edge_count, so route must contain n + 1 nodes.
        if len(route_tokens) != n + 1:
            raise ValueError(
                f"Route node count mismatch for vehicle {vehicle_index}: expected {n + 1}, got {len(route_tokens)}"
            )

        if i >= len(lines):
            raise ValueError(f"Missing cleaned-street line for vehicle {vehicle_index}")

        # Cleaned-street line can be empty by specification.
        i += 1

    if i != len(lines):
        # Trailing lines are often tolerated, but we keep this strict to avoid ambiguity.
        raise ValueError("Unexpected trailing lines in submission file")


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def first_vehicle_counts(path: str) -> Tuple[int, int]:
    with open(path, "r", encoding="ascii") as f:
        lines = f.read().splitlines()
    if len(lines) < 3:
        raise ValueError("Submission has fewer than 3 lines")
    declared = int(lines[1].strip())
    tokens = len([tok for tok in lines[2].split(" ") if tok])
    return declared, tokens


def main() -> None:
    parser = argparse.ArgumentParser(description="Street Cleaning heuristic solver")
    parser.add_argument("--input", required=True, help="Path to input instance")
    parser.add_argument("--output", required=True, help="Path to output submission")
    args = parser.parse_args()

    problem = parse_problem(args.input)
    vehicles = solve(problem)
    write_submission(args.output, problem, vehicles)

    validate_submission_file(args.output)

    declared, tokens = first_vehicle_counts(args.output)
    digest = file_sha256(args.output)
    print(f"WROTE: {args.output}")
    print(f"SHA256: {digest}")
    print(f"VEHICLE0_ROUTE_COUNT: declared_edges={declared} tokens(nodes)={tokens} expected_nodes={declared + 1}")


if __name__ == "__main__":
    main()
