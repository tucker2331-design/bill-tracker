---
tags: [ny, architecture, bill-pipeline]
updated: 2026-06-24
status: active
---

# New York Bill Pipeline

## Data flow

```
NY_OPENLEG_API_KEY
  -> NYOpenLegClient
  -> /api/3/bills/{sessionYear}?limit=1000&offset=N&full=true
  -> bill_to_record()
  -> records + completeness
  -> NY_Bill_Tracker tab (default) + R1 completeness JSON
```

## Source-to-field mapping

| Product field | OpenLeg source |
|---|---|
| Bill | `basePrintNo` / `printNo` |
| Title | `title` |
| Status (LIS) | `status.statusDesc` / `status.statusType` |
| Outcome | structural-first `signed`; veto from `vetoMessages` + veto status; then status fallback |
| Patron | `sponsor.member.fullName` |
| Patron ID | `sponsor.member.memberId` |
| Chamber | `billType.chamber` |
| Crossed Over | controlled status/milestone fields naming the opposite chamber |
| Last Committee | `status.committeeName`, fallback latest `pastCommittees` |
| Referrals | distinct sequential `pastCommittees` |
| Latest Vote | latest `votes.items[]` by `voteDate`, summarized from `memberVotes` |
| History | sorted `actions.items[]` by `(date, sequenceNo)` |
| Upcoming | intentionally empty in pass 1 until a validated NY meeting source exists |
| Source | `NY OpenLegislation` |

## Safety and honesty rules

- Keep Virginia and New York engines in separate files until the common abstraction is proven.
- Raw OpenLeg status is always retained; `outcome` is a convenience label.
- Do not infer a complete meeting calendar from Senate-centered endpoints.
- Completeness metrics always include denominators/rates where useful.
- A missing `NY_OPENLEG_API_KEY` is a hard failure, not an empty output.

## Known differences from Virginia

- Virginia has bulk CSV blobs (`HISTORY.CSV`, `BILLS.CSV`, `DOCKET.CSV`, `VOTE.CSV`) and LIS-specific structural refids.
- New York has a richer JSON bill response, including actions, votes, sponsor, summary, past committees, and agenda references.
- New York's public OpenLeg docs warn that Assembly calendar/committee data is not available through those Senate OpenLeg endpoints, so the calendar worker cannot be a straight source swap.
