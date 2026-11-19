"""JSON decoding for the complete, versioned run payload."""

from src.domain import (
    ConditionTrials, Criticality, CriticalityReport, Delivery, Edge, NetworkRef,
    NetworkSnapshot, Node, RunDetails, RuntimeVersions,
)


def decode_details(data: dict) -> RunDetails:
    snapshot = data["snapshot"]
    data["snapshot"] = NetworkSnapshot(
        NetworkRef(**snapshot["ref"]), snapshot["display_name"],
        tuple(Node(**node) for node in snapshot["nodes"]),
        tuple(Edge(**edge) for edge in snapshot["edges"]),
    )
    data["versions"] = RuntimeVersions(**data["versions"])
    criticality = data["criticality"]
    data["criticality"] = CriticalityReport(
        tuple(criticality["candidate_ids"]), criticality["trial_count"], criticality["baseline_fragility"],
        tuple(Criticality(**item) for item in criticality["ranking"]),
    )
    data["trials"] = ConditionTrials(**{
        condition: tuple(
            Delivery(tuple(item["path"]) if item["path"] is not None else None,
                     item["transit_hours"], item["end_to_end_hours"])
            for item in deliveries
        )
        for condition, deliveries in data["trials"].items()
    })
    return RunDetails(**data)
