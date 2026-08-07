"""Deterministic dependency ordering for manifest assignments."""

import heapq


def topological_assignments(assignments, dependencies):
    """Return a stable producer-before-consumer ordering.

    Dependencies involving subproblems outside the selected assignment set are
    retained as task context but do not create graph nodes for this protocol.
    """

    assignments = list(assignments)
    by_id = {item.get("subproblem_id"): item for item in assignments}
    position = {
        item.get("subproblem_id"): index for index, item in enumerate(assignments)
    }
    indegree = {node: 0 for node in by_id}
    outgoing = {node: set() for node in by_id}

    for dependency in dependencies:
        producer = dependency.get("producer_subproblem")
        consumer = dependency.get("consumer_subproblem")
        if producer not in by_id or consumer not in by_id or producer == consumer:
            continue
        if consumer not in outgoing[producer]:
            outgoing[producer].add(consumer)
            indegree[consumer] += 1

    ready = [(position[node], node) for node, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    ordered_ids = []
    while ready:
        _, node = heapq.heappop(ready)
        ordered_ids.append(node)
        for consumer in sorted(outgoing[node], key=position.get):
            indegree[consumer] -= 1
            if indegree[consumer] == 0:
                heapq.heappush(ready, (position[consumer], consumer))

    cycle_nodes = [node for node in by_id if node not in ordered_ids]
    ordered_ids.extend(sorted(cycle_nodes, key=position.get))
    return [by_id[node] for node in ordered_ids], cycle_nodes


def path_in_scope(path, writable_paths):
    path = str(path).strip().lstrip("./")
    for writable in writable_paths:
        writable = str(writable).strip().rstrip("/").lstrip("./")
        if path == writable or path.startswith(writable + "/"):
            return True
    return False
