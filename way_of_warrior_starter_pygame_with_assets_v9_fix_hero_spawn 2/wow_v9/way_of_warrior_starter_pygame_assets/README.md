# Way of the Warrior — starter (Pygame + isometric grid)

## Quick start (Windows)
1. **First time**: double‑click `install_deps.bat` (creates `.venv`, installs `pygame`).
2. Run: double‑click `run_game.bat`.

If you want “one button”: double‑click `start.bat`.

### If PowerShell blocks venv activation
We **do not** need to activate the venv. The bat files run the venv Python directly:

```
.\.venv\Scripts\python.exe .\main.py
```

So you can ignore `Set-ExecutionPolicy` completely.

## Controls
- **LMB**: move hero to clicked tile
- **RMB**: also move (alternative)
- **WASD / arrows**: move camera
- **C**: center camera on hero
- **I**: toggle inventory UI
- **O**: toggle dialog UI
- **F1**: debug overlay
- **T**: teleport hero near the portal
- **E**: spawn enemies **(only if hero is close to the portal)**
- **ESC**: quit

## Notes
- UI/backdrop are **Diablo‑like placeholders**. For a public release, replace with your own / CC0 assets.
