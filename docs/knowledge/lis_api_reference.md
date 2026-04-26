# Virginia LIS API Reference

## Authentication
All API calls require `WebAPIKey` header: `81D70A54-FCDC-4023-A00B-A3FD114D5984`
Accept header: `application/json`

## Endpoints

### Session API
`GET https://lis.virginia.gov/Session/api/GetSessionListAsync`
- Returns all 58 sessions back to 1994
- Key fields: SessionCode, SessionYear, IsActive, IsDefault, SessionEvents[]
- SessionEvents contain: EventName, ActualDate, ProjectedDate
- Event types: "Session Start", "Adjournment", "Prefile Date", "Reconvene"

### Committee API
`GET https://lis.virginia.gov/Committee/api/getcommitteelistasync?sessionCode={code}`
- Returns committees for a given session
- Key fields: CommitteeID, Name, CommitteeNumber (H01-H24, S01-S13), ChamberCode (H/S), ParentCommitteeID
- ParentCommitteeID is null for top-level committees, integer for subcommittees
- Session 261: 25 top-level committees confirmed

### Schedule API
`GET https://lis.virginia.gov/Schedule/api/getschedulelistasync?sessionCode={code}`
- Returns all scheduled meetings for a session
- Key fields: OwnerName, ScheduleDate, ScheduleTime, Description (HTML), IsCancelled
- Description may contain agenda links (HTML href)
- Session 261: 3,310 entries confirmed 1:1 with LIS website

## Data Sources (Azure Blob)

### HISTORY.CSV
`https://lis.blob.core.windows.net/lisfiles/{sessionYear}/HISTORY.CSV`
- Alternative: `https://blob.lis.virginia.gov/lisfiles/{sessionYear}/HISTORY.CSV`
- Session 261 (year 2026): 60,694 rows
- Key columns: BillNumber, HistoryDate, Description, History_refid
- History_refid encodes committee codes: "H14" (direct), "H14V2610034" (vote-style)

### DOCKET.CSV
`https://lis.blob.core.windows.net/lisfiles/{sessionYear}/DOCKET.CSV`
- Committee meeting bill assignments
- Senate committees S01-S13 confirmed
- Key columns: bill number, date, committee/description

## Known Quirks
- Schedule API ScheduleTime can be relative ("upon adjournment of the Senate")
- Description field is HTML, may contain links to PDF agendas
- HISTORY.CSV encoding is ISO-8859-1, not UTF-8
- Some blob URLs use different subdomain patterns (blob.lis vs lis.blob)
- History_refid may be empty for some action types (floor actions, executive actions)
