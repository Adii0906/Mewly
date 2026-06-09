# Mewly Behavior System

A simple, natural companion cat that reacts to your activity.

## Four Core States

### 🖥️ **CODE**
- **Trigger**: IDE is focused (VS Code, Cursor, Windsurf) OR you're typing
- **Animation**: Attentive, working alongside you  
- **Feel**: "I see you're coding"
- **Minimum Duration**: ~4 seconds

### 🪑 **IDLE**  
- **Trigger**: You're present but not coding
- **Animation**: Calm sitting, subtle movements
- **Feel**: "I'm here with you"
- **Minimum Duration**: ~3 seconds

### 🚶 **WALK**
- **Trigger**: Occasionally during IDLE state
- **Animation**: Short walk across screen
- **Feel**: "I'm stretching my legs"
- **Minimum Duration**: ~2 seconds
- **Returns to**: IDLE when finished

### 😴 **SLEEP**
- **Trigger**: 10+ seconds of no keyboard or mouse activity
- **Animation**: Peaceful napping
- **Feel**: "Time to rest"  
- **Minimum Duration**: ~5 seconds
- **Wakes on**: Keyboard or mouse activity

## State Priority

```
CODE (highest priority)
  ↓
SLEEP
  ↓
WALK
  ↓
IDLE (lowest priority)
```

## Activity Detection

### What triggers CODE
- IDE in focus (VS Code, Cursor, Windsurf)
- Any keyboard typing (≥1 WPM)

### What triggers SLEEP
- 10 seconds with zero keyboard activity
- Zero mouse movement
- Both conditions required

### What allows WALK
- During IDLE state only
- Random timing
- Brief duration (~2 seconds)

### What allows IDLE
- No IDE active
- No typing
- Includes time spent browsing, reading, thinking

## Animation Speeds

- **IDLE**: 6 FPS — calm and relaxed
- **CODE**: 7 FPS — attentive but calm
- **WALK**: 8 FPS — natural pace  
- **SLEEP**: 4 FPS — slow and peaceful
- **JUMP**: 10 FPS — quick bursts (during IDLE)

## Configuration

Edit these in `config.py`:

```python
# How long before sleep (seconds)
INACTIVITY_SLEEP_SECS = 10

# IDEs that count as coding
IDE_PROCESSES = ["code", "cursor", "windsurf", "code - insiders"]

# Typing detection window (seconds)
TYPING_WINDOW_SECS = 5
```

## Examples

### Scenario 1: Working in Code
```
You open VS Code and start typing
→ CODE state
  
You continue coding for 10 minutes
→ Stays in CODE state

You pause to think (no typing)
→ CODE state continues (didn't hit 10 sec threshold)

You resume coding
→ Still CODE state
```

### Scenario 2: Taking a Break  
```
You finish coding and switch to browser
→ CODE state initially

After a few seconds, IDLE state
→ Cat sits and watches

You close browser and step away
→ IDLE for 10 seconds
→ SLEEP state
→ Cat naps peacefully

You move mouse or type
→ Cat wakes up
→ CODE state (if IDE active) or IDLE state
```

### Scenario 3: Natural Wandering
```
You're idle, not coding
→ IDLE state

After a bit, randomly trigger WALK
→ WALK animation (brief)

Walk finishes
→ Back to IDLE

This repeats occasionally
→ Natural, believable behavior
```

## Visual Behavior

The cat should feel **alive and responsive**:

- **Responds quickly** to activity changes (within 1-2 seconds)
- **Stays in state** long enough to feel meaningful (3-5 seconds minimum)
- **Never hyperactive** — smooth, calm animations
- **Understands context** — knows when you're working vs. present vs. away
- **Wakes naturally** — smooth transition from sleep

## Technical Details

### State Machine Priority
1. **Forced states** (manual DEBUG/TASK triggers)
2. **Productivity** (IDE active, typing, Pomodoro)
3. **Movement** (WALK during IDLE)
4. **Inactivity** (SLEEP)

### No Multi-State Rendering
- Only ONE animation plays at a time
- Only ONE state is active at a time
- No overlapping cats or animations

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Cat sleeps too fast | Increase `INACTIVITY_SLEEP_SECS` to 20 or 30 |
| Cat won't detect VS Code | Check IDE name in `IDE_PROCESSES` |
| Cat switches states too fast | Increase `STATE_MIN_TICKS` values |
| Animations feel slow | Increase FPS in `STATE_FPS_OVERRIDE` |

## Files

- `config.py` — All settings and thresholds
- `productivity_manager.py` — Activity detection  
- `state_manager.py` — State machine logic
- `~/.coding_cat/cat.log` — Debug logs

---

**Simple. Natural. Alive.**
