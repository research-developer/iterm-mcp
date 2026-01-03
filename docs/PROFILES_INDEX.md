# iTerm2 Profiles Documentation Index

Complete reference suite for implementing team-based visual distinction in iterm-mcp using iTerm2's Profile API.

---

## Quick Navigation

Choose your reading path based on your needs:

### For Implementation
1. Start with **[PROFILES_CHEATSHEET.md](./PROFILES_CHEATSHEET.md)** - minimal working examples
2. Read **[PROFILES_INTEGRATION.md](./PROFILES_INTEGRATION.md)** - implementation guide with code
3. Reference **[PROFILES.md](./PROFILES.md)** when needed for detailed information

### For API Details
1. Start with **[PROFILES.md](./PROFILES.md)** - complete API reference
2. Look up specific operations in the Quick Reference section
3. Find examples for your use case in the Examples section

### For Troubleshooting
1. Check Common Mistakes in **[PROFILES_CHEATSHEET.md](./PROFILES_CHEATSHEET.md)**
2. See Integration section in **[PROFILES.md](./PROFILES.md)**
3. Review Troubleshooting in **[PROFILES_INTEGRATION.md](./PROFILES_INTEGRATION.md)**

---

## Document Overview

### PROFILES.md (854 lines)

**Comprehensive technical reference covering all Profile API features.**

**Contents:**
- Quick reference for common operations
- Core concepts (GUIDs, names, identification)
- Visual indicators (tab colors, badges, cursor guides)
- Color manipulation (HSL system, team distribution)
- Async patterns and error handling
- Team-based profile workflows
- Integration with AgentRegistry and NotificationManager
- 7 complete working examples
- Performance optimization notes
- Full method reference table (read-only properties and async setters)

**Best For:**
- Understanding the complete Profile API
- Finding async patterns for your use case
- Integration examples with AgentRegistry
- Performance tuning and caching strategies
- Color math and HSL distribution

**Key Sections:**
- Quick Reference: Most common 10 operations
- Color Manipulation: HSL theory + team color distribution algorithm
- Team-Based Profiles: Session-profile relationships
- Integration Points: How profiles connect to your existing code
- Examples: 4 progressively complex examples from basic to monitoring

---

### PROFILES_INTEGRATION.md (598 lines)

**Step-by-step implementation guide with production-ready code.**

**Contents:**
- ProfileManager module (complete implementation)
- Integration with AgentRegistry
- Integration with NotificationManager
- MCP server tools for profile management
- 3 usage examples (setup, task execution, multi-agent monitoring)
- Configuration format (YAML)
- Unit tests
- Migration checklist

**Best For:**
- Adding profile support to iterm-mcp
- Copy-paste ready code for ProfileManager
- Understanding integration points
- Setting up team visual distinction
- Testing profile features

**Key Sections:**
- ProfileManager: Complete class with caching and error handling
- AgentRegistry Integration: Tracking profile GUIDs in metadata
- NotificationManager Integration: Updating profiles on status change
- MCP Tools: 3 tools for Claude to manage profiles
- Usage Examples: Practical patterns for common tasks
- Testing: pytest-style test examples
- Migration Checklist: Step-by-step deployment guide

---

### PROFILES_CHEATSHEET.md (375 lines)

**Quick reference for most common operations (minimal code).**

**Contents:**
- Setup and imports
- Getting profiles (by GUID, default)
- Tab colors (create, apply, disable)
- Common color presets
- Badge text and appearance
- Profile properties (name, GUID)
- Batch updates with asyncio.gather()
- Error handling template
- Cursor settings
- Team color generation algorithm
- Agent metadata patterns
- Profile caching pattern
- Complete minimal example
- Properties reference table
- Common mistakes and fixes

**Best For:**
- Quick lookup of syntax
- Copy-paste code snippets
- Learning by example (minimal working code)
- Remembering parameter ranges
- Checking correct async/await usage

**Key Sections:**
- One-liners for common operations
- Complete minimal example (runnable)
- Properties reference table
- Common mistakes section with fixes
- Quick team color algorithm

---

## Recommended Reading Order

### First Time Setup

1. **PROFILES_CHEATSHEET.md** - Learn the syntax (15 min)
   - See how colors work (HSL)
   - Understand tab colors and badges
   - Run the minimal example

2. **PROFILES_INTEGRATION.md** - Implement ProfileManager (30 min)
   - Copy ProfileManager class
   - Add to your codebase
   - Update tests

3. **PROFILES.md** - Deep dive on integration (30 min)
   - Understand AgentRegistry.metadata usage
   - Learn about profile caching
   - See monitoring examples

### Implementation Workflow

```
1. Read PROFILES_CHEATSHEET.md (minimal example)
   ↓
2. Copy code from PROFILES_INTEGRATION.md (ProfileManager)
   ↓
3. Add to your FastMCP server (PROFILES_INTEGRATION.md section 4)
   ↓
4. Test with PROFILES_INTEGRATION.md (section 7)
   ↓
5. Reference PROFILES.md for advanced patterns
```

### When You Need Something Specific

| Need | Document | Section |
|------|----------|---------|
| Create a color | CHEATSHEET | Common Colors / Create color |
| Set tab color | CHEATSHEET | Tab Colors |
| Set badge text | CHEATSHEET | Badge Text |
| Store profile GUID in agent | INTEGRATION | Example 1: Team-Based Color System |
| Update agent status | INTEGRATION | ProfileManager.set_agent_status() |
| Batch update profiles | CHEATSHEET | Batch Updates |
| Handle profile not found | INTEGRATION | ProfileManager error handling |
| Generate team colors | CHEATSHEET | Generate Team Colors / PROFILES | Color Manipulation |
| Understand HSL | PROFILES | Color Representation section |
| Implement caching | INTEGRATION | ProfileManager._profile_cache |
| Test profiles | INTEGRATION | Testing Profile Features section |

---

## Key Concepts Summary

### Profile Identification
- **GUID**: Immutable ID for persistent reference
- **Name**: Mutable, human-readable identifier
- Store GUIDs in AgentRegistry.metadata for recovery after session restart

### Visual Distinction for Teams
- **Tab Color** (primary): HSL Color with hue distributed evenly across teams
- **Badge Text** (secondary): Team name + status (e.g., "backend: RUNNING")
- **Badge Color** (optional): Usually matches team color

### Color Model (HSL)
- **Hue** (0-360°): Color wheel position
  - 0°: Red, 120°: Green, 220°: Blue
  - Distribute evenly: `hue = (team_index / total_teams) * 360`
- **Saturation** (0-100%): Color intensity (75% typical for distinction)
- **Lightness** (0-100%): Brightness (40% for readable on both light/dark terminals)

### Integration Points
- **AgentRegistry**: Store profile_guid in agent.metadata
- **NotificationManager**: Update badge on status change
- **Session Management**: Apply profile colors to new sessions
- **MCP Tools**: Add tools for Claude to manage profiles

---

## Common Tasks Quick Links

### Task: Set up team-based colors

1. Read: PROFILES_CHEATSHEET.md → Common Colors
2. Implement: PROFILES_INTEGRATION.md → ProfileManager class
3. Configure: PROFILES_INTEGRATION.md → Configuration section
4. Deploy: PROFILES_INTEGRATION.md → Migration Checklist

### Task: Update agent status badge

1. Quick lookup: PROFILES_CHEATSHEET.md → Badge Text section
2. Implementation: PROFILES_INTEGRATION.md → ProfileManager.set_agent_status()
3. Integration: PROFILES_INTEGRATION.md → NotificationManager Integration
4. Testing: PROFILES_INTEGRATION.md → test_set_agent_status

### Task: Create and register a new team

1. Pattern: PROFILES_INTEGRATION.md → Example 1
2. Full API: PROFILES.md → Team-Based Profiles section
3. AgentRegistry integration: PROFILES.md → Integration with AgentRegistry
4. Complete example: PROFILES.md → Example 1: Team-Based Color System

### Task: Generate colors for N teams

1. Algorithm: PROFILES_CHEATSHEET.md → Generate Team Colors
2. Details: PROFILES.md → Team Color Distribution
3. Complete example: PROFILES.md → Example 1: Team-Based Color System
4. Code template: PROFILES_INTEGRATION.md → ProfileManager.__init__

### Task: Handle profile not found error

1. Pattern: PROFILES_CHEATSHEET.md → Error Handling
2. Complete: PROFILES_INTEGRATION.md → ProfileManager.get_profile_by_guid()
3. Advanced: PROFILES.md → Async Patterns / Error Handling

---

## File Locations

```
/Users/preston/MCP/iterm-mcp/docs/
├── PROFILES.md                  # Complete technical reference (854 lines)
├── PROFILES_INTEGRATION.md      # Implementation guide with code (598 lines)
├── PROFILES_CHEATSHEET.md       # Quick reference (375 lines)
└── PROFILES_INDEX.md            # This file (navigation guide)
```

---

## Related Documentation

- **Session API**: See `SESSION.md` for iTerm2 session management
- **Agent Registry**: See `AGENTS.md` or `core/agents.py` for agent metadata
- **Notification System**: See `FEEDBACK.md` or `core/feedback.py` for status updates
- **iTerm2 Official Docs**: [iterm2.com/python-api/profile.html](https://iterm2.com/python-api/profile.html)

---

## Implementation Checklist

Use this checklist when implementing profile support:

- [ ] **Read PROFILES_CHEATSHEET.md** to understand syntax
- [ ] **Copy ProfileManager code** from PROFILES_INTEGRATION.md section 1
- [ ] **Add to imports**: Update your module imports
- [ ] **Integrate with AgentRegistry**: Store profile_guid in metadata
- [ ] **Integrate with NotificationManager**: Update badges on status change
- [ ] **Add MCP tools**: Copy tools from PROFILES_INTEGRATION.md section 4
- [ ] **Configure colors**: Update TEAM_COLORS in ProfileManager
- [ ] **Add tests**: Use test templates from PROFILES_INTEGRATION.md section 7
- [ ] **Update server**: Initialize ProfileManager in FastMCP startup
- [ ] **Test locally**: Run tests with PROFILES_INTEGRATION.md examples
- [ ] **Deploy**: Update servers and test with real agents

---

## Troubleshooting Guide

### "Profile not found" Error
**Solution:** Check PROFILES_CHEATSHEET.md → Error Handling
**Root cause:** GUID invalid or profile deleted
**Fix:** Re-create profile or update agent.metadata

### Tab color not displaying
**Solution:** Check PROFILES_CHEATSHEET.md → Tab Colors section
**Root cause:** `use_tab_color` is False
**Fix:** Call `await profile.async_set_use_tab_color(True)`

### Badge text truncated or wrapped
**Solution:** Check PROFILES_CHEATSHEET.md → Keep short
**Root cause:** Text longer than 30 chars
**Fix:** Truncate to ~25 chars or use abbreviations

### Async/await syntax errors
**Solution:** Check PROFILES_CHEATSHEET.md → Common Mistakes
**Root cause:** Missing `await` on async methods
**Fix:** All `async_*` methods must be awaited

### Profile cache stale
**Solution:** See PROFILES_INTEGRATION.md → ProfileManager
**Root cause:** Cache not cleared after external updates
**Fix:** Call `profile_manager.clear_cache()`

---

## Version Information

**Created:** January 2, 2026
**iTerm2 API Version:** Latest Python API (3.x compatible)
**Python Version:** 3.8+
**Tested with:** iterm2 version from PyPI

---

## Contributing

When updating these docs:

1. Keep PROFILES.md as the complete reference
2. Keep PROFILES_INTEGRATION.md as production code examples
3. Keep PROFILES_CHEATSHEET.md minimal (one-liners)
4. Update PROFILES_INDEX.md when adding new sections
5. Ensure all code examples are tested

---

## Quick Links

- [Full API Reference](./PROFILES.md)
- [Implementation Guide](./PROFILES_INTEGRATION.md)
- [Cheat Sheet](./PROFILES_CHEATSHEET.md)
- [iTerm2 Official](https://iterm2.com/python-api/profile.html)
