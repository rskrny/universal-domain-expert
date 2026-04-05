"""
Orchestrator -- the Jarvis cognition layer.

Sits between perception (intelligence/) and action (lark delivery, social posting).
Reads all inputs -- memory files, deadlines, routing patterns, project state --
and produces prioritized action recommendations.

Three modules:
  project_scanner.py  -- Extract structured state from memory files
  planner.py          -- Reason across all inputs, produce daily action plan
  action_tracker.py   -- Track recommendations and whether they were acted on
"""
