#!/usr/bin/env python3
from pathlib import Path

CAP = {"S": 10, "M": 20, "L": 30}
CURRENT = {
    "train_a": 0.537715873,
    "train_b": 0.854685587,
    "train_n": 0.864582645,
    "m": 0.640016963,
}


def score(name: str, sub_path: str):
    inst = Path(f"inputs/{name}.txt").read_text(encoding="ascii").splitlines()
    _, m_s, t_s, c_s, _, a_s = inst[0].split()
    m = int(m_s)
    t_limit = int(t_s)
    c = int(c_s)
    alpha = float(a_s)

    edge = {}
    cat = {}
    req = {}
    length = {}
    for eid in range(m):
        a, b, d, ct, l, category, r = inst[1 + eid].split()
        a = int(a)
        b = int(b)
        d = int(d)
        ct = int(ct)
        l = int(l)
        r = int(r)
        edge[(a, b)] = ct
        if d == 2:
            edge[(b, a)] = ct
        cat[eid] = category
        req[eid] = r
        length[eid] = l

    veh = inst[1 + m].split()
    lines = Path(sub_path).read_text(encoding="ascii").splitlines()

    cleaned = set()
    waste = 0.0
    valid = True
    i = 1
    for vi in range(c):
        n = int(lines[i])
        route = [int(x) for x in lines[i + 1].split()]
        cl = [int(x) for x in lines[i + 2].split()] if lines[i + 2].strip() else []
        i += 3

        if len(route) != n + 1:
            valid = False

        tt = 0
        for u, v in zip(route, route[1:]):
            if (u, v) not in edge:
                valid = False
                tt = t_limit + 1
                break
            tt += edge[(u, v)]
        if tt > t_limit:
            valid = False

        for eid in cl:
            if cat[eid] in ("M", "O"):
                waste += (CAP[veh[vi]] - req[eid]) * (length[eid] / 1000.0)
        cleaned.update(cl)

    mandatory = {e for e in range(m) if cat[e] == "M"}
    if mandatory - cleaned:
        valid = False

    cleanable = [e for e in range(m) if cat[e] in ("M", "O")]
    l_max = sum(length[e] for e in cleanable)
    w_max = sum((30 - req[e]) * (length[e] / 1000.0) for e in cleanable)

    covered_len = sum(length[e] for e in cleaned if cat[e] in ("M", "O"))
    coverage = (covered_len / l_max) if l_max else 0.0
    efficiency = (1.0 - waste / w_max) if w_max else 1.0
    score_val = alpha * coverage + (1.0 - alpha) * efficiency
    return valid, score_val


def main():
    for name in ["train_a", "train_b", "train_n", "m"]:
        sub = f"submissions/{name}_v2.txt"
        if not Path(sub).exists():
            print(name, "missing", sub)
            continue
        valid, sc = score(name, sub)
        delta = sc - CURRENT[name]
        print(name, "v2_valid", valid, "v2_score", round(sc, 9), "delta_vs_best", round(delta, 9))


if __name__ == "__main__":
    main()
