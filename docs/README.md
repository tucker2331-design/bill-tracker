# Project Knowledge Base ("File Brain")

Persistent project memory for any AI or human working on this codebase. Each directory serves a specific purpose:

## Directory Structure

### `/architecture`
System design decisions, data flow diagrams, API contracts, and integration plans.
- Why things are built the way they are
- What the dependencies between components are
- How data flows from LIS -> processing -> Google Sheets

### `/testing`
Test plans, test results, regression baselines, and coverage maps.
- Which edge cases have been tested and their outcomes
- Before/after metrics for every change
- The crossover week (Feb 9-13) baseline numbers

### `/failures`
Post-mortems, known bugs, things that broke and why, and how they were fixed.
- Every assumption that turned out to be wrong
- Root cause analyses
- Patterns of failure to watch for

### `/ideas`
Future improvements, feature requests, optimization ideas, and research notes.
- Things we want to do but haven't prioritized yet
- Trade-off analyses for different approaches
- Performance optimization candidates

### `/knowledge`
Domain knowledge about Virginia LIS, legislative process, data quirks, and API behavior.
- How LIS structures its data (refids, committee codes, session codes)
- Known LIS API quirks and undocumented behavior
- Legislative process knowledge that affects code logic
