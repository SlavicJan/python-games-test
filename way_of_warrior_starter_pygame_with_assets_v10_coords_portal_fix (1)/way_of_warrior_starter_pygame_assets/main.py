import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import pygame

# -----------------------------
# Config
# -----------------------------
W, H = 1280, 720
FPS = 60

TILE_W = 64
TILE_H = 32
GRID_W, GRID_H = 40, 40

# Shift isometric world so X never goes negative (keeps math consistent)
ISO_ORIGIN_X = (GRID_H - 1) * (TILE_W // 2)
ISO_ORIGIN_Y = 0


BG = (18, 20, 24)
GRID_COL = (44, 48, 58)
GRID_COL_DARK = (34, 38, 46)

UI_MARGIN = 18
UI_TOP = 28  # safe space for fancy frame
UI_RIGHT = 18

ASSETS_DIR = "assets"


# -----------------------------
# Helpers: image fit
# -----------------------------
def load_img(name: str) -> Optional[pygame.Surface]:
    try:
        return pygame.image.load(f"{ASSETS_DIR}/{name}").convert_alpha()
    except Exception:
        return None


def scale_contain(surf: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
    """Scale surf to fit inside (max_w,max_h) keeping aspect."""
    w, h = surf.get_width(), surf.get_height()
    if w <= 0 or h <= 0:
        return surf
    s = min(max_w / w, max_h / h, 1.0)  # never upscale
    if abs(s - 1.0) < 1e-6:
        return surf
    return pygame.transform.smoothscale(surf, (int(w * s), int(h * s)))


def scale_cover(surf: pygame.Surface, target_w: int, target_h: int) -> pygame.Surface:
    """Scale surf to fully cover (target_w,target_h) and center-crop."""
    w, h = surf.get_width(), surf.get_height()
    if w <= 0 or h <= 0:
        return surf
    s = max(target_w / w, target_h / h)
    new_w, new_h = int(w * s), int(h * s)
    scaled = pygame.transform.smoothscale(surf, (new_w, new_h))
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    return scaled.subsurface(pygame.Rect(x, y, target_w, target_h)).copy()


def load_ui(name: str, *, mode: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
    surf = load_img(name)
    if not surf:
        return None
    if mode == "contain":
        return scale_contain(surf, size[0], size[1])
    if mode == "cover":
        return scale_cover(surf, size[0], size[1])
    return surf


def compute_safe_rect_from_frame(
    frame: pygame.Surface,
    *,
    alpha_threshold: int = 8,
    padding: int = 12,
) -> pygame.Rect:
    """Compute the interactive "safe" rectangle inside a decorative frame.

    The UI frame is expected to have an *opaque border* and a *transparent center*.
    We detect the transparent window by sampling the center row/column and finding
    the continuous run of near-transparent pixels.

    This runs once at startup and avoids numpy/surfarray dependencies.
    """
    w, h = frame.get_size()
    full = pygame.Rect(0, 0, w, h)

    # Surface might not have per-pixel alpha; if so, just return a reasonable inset.
    if frame.get_masks()[3] == 0:
        fallback = full.inflate(-2 * (padding + 80), -2 * (padding + 80))
        return fallback.clamp(full)

    cx, cy = w // 2, h // 2

    def a(x: int, y: int) -> int:
        return frame.get_at((x, y)).a

    # If center is not transparent, fallback to a sane inset.
    if a(cx, cy) > alpha_threshold:
        fallback = full.inflate(-2 * (padding + 80), -2 * (padding + 80))
        return fallback.clamp(full)

    # Horizontal scan (center row)
    x0 = cx
    while x0 > 0 and a(x0, cy) <= alpha_threshold:
        x0 -= 1
    left = x0 + 1

    x1 = cx
    while x1 < w - 1 and a(x1, cy) <= alpha_threshold:
        x1 += 1
    right = x1 - 1

    # Vertical scan (center column)
    y0 = cy
    while y0 > 0 and a(cx, y0) <= alpha_threshold:
        y0 -= 1
    top = y0 + 1

    y1 = cy
    while y1 < h - 1 and a(cx, y1) <= alpha_threshold:
        y1 += 1
    bottom = y1 - 1

    rect = pygame.Rect(left, top, max(1, right - left + 1), max(1, bottom - top + 1))
    # Keep a little distance from the frame border.
    rect.inflate_ip(-2 * padding, -2 * padding)
    if rect.w < 50 or rect.h < 50:
        fallback = full.inflate(-2 * (padding + 80), -2 * (padding + 80))
        return fallback.clamp(full)
    return rect.clamp(full)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


# -----------------------------
# Iso math + A*
# -----------------------------
def grid_to_iso(gx: int, gy: int) -> Tuple[int, int]:
    """Convert grid cell (gx, gy) to isometric world coords (tile top-left)."""
    iso_x = (gx - gy) * (TILE_W // 2) + ISO_ORIGIN_X
    iso_y = (gx + gy) * (TILE_H // 2) + ISO_ORIGIN_Y
    return iso_x, iso_y


def iso_to_grid(ix: float, iy: float) -> Tuple[int, int]:
    """Inverse of grid_to_iso (approx), expects world coords with same origin shift."""
    ix -= ISO_ORIGIN_X
    iy -= ISO_ORIGIN_Y
    gx = (ix / (TILE_W / 2) + iy / (TILE_H / 2)) / 2
    gy = (iy / (TILE_H / 2) - ix / (TILE_W / 2)) / 2
    return int(round(gx)), int(round(gy))


def astar(start: Tuple[int, int], goal: Tuple[int, int], blocked: set) -> List[Tuple[int, int]]:
    if start == goal:
        return [start]
    if goal in blocked:
        return []
    def h(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def neighbors(n):
        x, y = n
        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H and (nx, ny) not in blocked:
                yield (nx, ny)

    open_set = {start}
    came: Dict[Tuple[int,int], Tuple[int,int]] = {}
    g = {start: 0}
    f = {start: h(start, goal)}

    while open_set:
        current = min(open_set, key=lambda n: f.get(n, 10**9))
        if current == goal:
            path = [current]
            while current in came:
                current = came[current]
                path.append(current)
            path.reverse()
            return path

        open_set.remove(current)
        for nb in neighbors(current):
            tentative = g[current] + 1
            if tentative < g.get(nb, 10**9):
                came[nb] = current
                g[nb] = tentative
                f[nb] = tentative + h(nb, goal)
                open_set.add(nb)

    return []


# -----------------------------
# Entities
# -----------------------------
@dataclass
class Hero:
    gx: int
    gy: int
    hp: int = 100
    mp: int = 50
    level: int = 1
    gold: int = 0

    path: Optional[List[Tuple[int, int]]] = None
    step_timer: float = 0.0

    def set_path(self, p: List[Tuple[int, int]]):
        if p and p[0] == (self.gx, self.gy):
            p = p[1:]
        self.path = p

    def update(self, dt: float):
        if not self.path:
            return

        self.step_timer -= dt
        if self.step_timer > 0:
            return

        nx, ny = self.path[0]
        self.gx, self.gy = nx, ny
        self.path.pop(0)
        self.step_timer = 0.10  # seconds per tile


@dataclass
class Portal:
    gx: int
    gy: int
    active: bool = True
    t: float = 0.0

    def update(self, dt: float):
        self.t += dt


@dataclass
class Enemy:
    gx: int
    gy: int
    hp: int = 10


# -----------------------------
# Map
# -----------------------------


class IsoMap:
    def __init__(self):
        self.blocked = set()
        random.seed(7)
        for _ in range(120):
            x = random.randint(0, GRID_W - 1)
            y = random.randint(0, GRID_H - 1)
            if (x, y) not in [(10,10), (20,20)]:
                self.blocked.add((x, y))

    def draw_grid(self, surf: pygame.Surface, cam_x: int, cam_y: int):
        # draw only visible-ish rows to keep it light
        for y in range(GRID_H):
            for x in range(GRID_W):
                iso_x, iso_y = grid_to_iso(x, y)
                sx = cam_x + iso_x
                sy = cam_y + iso_y

                # quick cull
                if sx < -TILE_W or sx > W + TILE_W or sy < -TILE_H or sy > H + TILE_H:
                    continue

                c = GRID_COL_DARK if (x + y) % 2 else GRID_COL
                if (x, y) in self.blocked:
                    c = (40, 40, 44)

                pts = [
                    (sx, sy + TILE_H // 2),
                    (sx + TILE_W // 2, sy),
                    (sx + TILE_W, sy + TILE_H // 2),
                    (sx + TILE_W // 2, sy + TILE_H),
                ]
                pygame.draw.polygon(surf, c, pts, 0)
                pygame.draw.polygon(surf, (0, 0, 0), pts, 1)
    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int, hero=None):
        """Draw map + markers.

        Important: EVERY marker uses the same coordinate system:
        - grid_to_iso returns world coords (tile top-left)
        - cam_x/cam_y are screen offsets for world origin
        - cell center is (iso_x + TILE_W/2, iso_y + TILE_H/2)
        """
        self.draw_grid(surf, cam_x, cam_y)

        def cell_center(gx: int, gy: int):
            ix, iy = grid_to_iso(gx, gy)
            return (cam_x + ix + TILE_W // 2, cam_y + iy + TILE_H // 2)

        # Portal marker (blue)
        px, py = cell_center(self.portal_gx, self.portal_gy)
        pygame.draw.circle(surf, (0, 180, 255), (px, py - 10), 12, 2)

        # Enemies (red)
        for e in self.enemies:
            ex, ey = cell_center(e.gx, e.gy)
            pygame.draw.circle(surf, (220, 50, 50), (ex, ey - 8), 7)

        if hero is None:
            return

        # Path dots (yellow)
        for tx, ty in hero.path:
            x, y = cell_center(tx, ty)
            pygame.draw.circle(surf, (255, 210, 80), (x, y - 4), 4)

        # Hero (white)
        hx, hy = cell_center(hero.gx, hero.gy)
        pygame.draw.circle(surf, (240, 240, 240), (hx, hy - 10), 7)


# -----------------------------
# UI helpers
# -----------------------------
def draw_hint(screen: pygame.Surface, font: pygame.font.Font, text: str):
    pad = 10
    s = font.render(text, True, (230, 230, 235))
    box = pygame.Surface((s.get_width() + pad*2, s.get_height() + pad*2), pygame.SRCALPHA)
    box.fill((0, 0, 0, 160))
    box.blit(s, (pad, pad))
    screen.blit(box, (UI_MARGIN, H - box.get_height() - UI_MARGIN))



def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Way of the Warrior — starter (Pygame + AI UI)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)

    # UI (auto-fit)
    ui_frame = load_ui("ui_frame_overlay.png", mode="cover", size=(W, H))
    ui_inventory = load_ui("ui_inventory_panel.png", mode="contain", size=(int(W*0.62), int(H*0.78)))
    ui_dialog = load_ui("ui_dialog.png", mode="contain", size=(int(W*0.78), int(H*0.48)))

    safe_rect = pygame.Rect(0, 0, W, H)
    if ui_frame:
        safe_rect = compute_safe_rect_from_frame(ui_frame, alpha_threshold=8, padding=12)

    iso = IsoMap()

    # Portal (center of map)
    portal = (GRID_W // 2, GRID_H // 2)
    # Keep IsoMap.portal in sync with the 'portal' used for spawning/interaction
    iso.portal_gx, iso.portal_gy = portal
    # Make sure the portal area is walkable (no random rocks blocking your demo)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            px, py = portal[0] + dx, portal[1] + dy
            if 0 <= px < GRID_W and 0 <= py < GRID_H:
                iso.blocked.discard((px, py))

    # Spawn hero near the portal (so you can test E immediately)
    hero = Hero(gx=portal[0]-4, gy=portal[1]+6)
    enemies: List[Enemy] = []
    msg = "ЛКМ/ПКМ: идти  |  I: инвентарь  |  O: диалог  |  F1: debug  |  E: портал"

    # Camera origin (screen pixel coords). Center on hero inside safe rect.
    hsx, hsy = grid_to_iso(hero.gx, hero.gy)
    cam_x = safe_rect.centerx - (hsx + TILE_W // 2)
    cam_y = safe_rect.centery - (hsy + TILE_H // 2)

    show_inv = False
    show_dialog = False
    debug = False

    def spawn_wave():
        nonlocal enemies, msg
        rnd = random.Random(pygame.time.get_ticks())
        spawned = 0
        for _ in range(40):
            gx = portal[0] + rnd.randrange(-4, 5)
            gy = portal[1] + rnd.randrange(-4, 5)
            if 0 <= gx < GRID_W and 0 <= gy < GRID_H and (gx, gy) not in iso.blocked and (gx, gy) != (hero.gx, hero.gy):
                enemies.append(Enemy(gx=gx, gy=gy, hp=rnd.randrange(6, 14)))
                spawned += 1
                if spawned >= 7:
                    break
        msg = f"Портал активирован: заспавнил {spawned} врагов. (Это пока кружочки, не пугайся.)"

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_i:
                    show_inv = not show_inv
                elif e.key == pygame.K_o:
                    show_dialog = not show_dialog
                elif e.key == pygame.K_F1:
                    debug = not debug
                elif e.key == pygame.K_c:
                    # Center camera on hero
                    hsx, hsy = grid_to_iso(hero.gx, hero.gy)
                    cam_x = safe_rect.centerx - (hsx + TILE_W // 2)
                    cam_y = safe_rect.centery - (hsy + TILE_H // 2)
                    msg = "Камера по герою."
                elif e.key == pygame.K_t:
                    # Teleport hero to portal (handy for testing)
                    hero.gx, hero.gy = portal
                    hero.path.clear()
                    hsx, hsy = grid_to_iso(hero.gx, hero.gy)
                    cam_x = safe_rect.centerx - (hsx + TILE_W // 2)
                    cam_y = safe_rect.centery - (hsy + TILE_H // 2)
                    msg = "Телепорт к порталу. Нажми E рядом — появятся враги."
                elif e.key == pygame.K_e:
                    # Activate portal if standing on it (or adjacent)
                    if abs(hero.gx - portal[0]) <= 1 and abs(hero.gy - portal[1]) <= 1:
                        spawn_wave()
                    else:
                        msg = "Подойди к порталу (в центре карты) и нажми E."

            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button in (1, 3):
                    mx, my = e.pos
                    # Ignore clicks outside playable window (behind UI)
                    if not safe_rect.collidepoint(mx, my):
                        continue
                    gx, gy = iso_to_grid(mx - cam_x, my - cam_y)
                    gx = max(0, min(GRID_W - 1, gx))
                    gy = max(0, min(GRID_H - 1, gy))
                    if (gx, gy) not in iso.blocked:
                        p = astar((hero.gx, hero.gy), (gx, gy), iso.blocked)
                        if p:
                            hero.set_path(p)

        keys = pygame.key.get_pressed()
        speed = (560 if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else 360) * dt
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            cam_x += int(speed)
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            cam_x -= int(speed)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            cam_y += int(speed)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            cam_y -= int(speed)

        hero.update(dt)

        screen.fill(BG)

        # Draw world clipped to safe rect (so it doesn't go under UI elements)
        screen.set_clip(safe_rect)
        iso.draw(screen, cam_x, cam_y, hero)

        # Draw portal marker
        psx, psy = grid_to_iso(portal[0], portal[1])
        px, py = int(psx + cam_x), int(psy + cam_y)
        t = pygame.time.get_ticks() / 1000.0
        r1 = int(18 + 4 * math.sin(t * 2.2))
        r2 = int(28 + 5 * math.sin(t * 1.3 + 1.0))
        pygame.draw.circle(screen, (40, 180, 255), (px, py - 10), r2, 3)
        pygame.draw.circle(screen, (120, 220, 255), (px, py - 10), r1, 2)
        pygame.draw.circle(screen, (40, 80, 120), (px, py - 10), 6)

        # Enemies
        for en in enemies:
            esx, esy = grid_to_iso(en.gx, en.gy)
            ex, ey = int(esx + cam_x), int(esy + cam_y)
            pygame.draw.circle(screen, (240, 90, 90), (ex, ey - 14), 10)
            pygame.draw.circle(screen, (0, 0, 0), (ex, ey - 14), 10, 2)
            # HP mini bar
            bar_w = 28
            hp_ratio = max(0.0, min(1.0, en.hp / 14.0))
            bx = ex - bar_w // 2
            by = ey - 30
            pygame.draw.rect(screen, (30, 30, 30), (bx, by, bar_w, 5))
            pygame.draw.rect(screen, (240, 90, 90), (bx, by, int(bar_w * hp_ratio), 5))

        screen.set_clip(None)

        # Top stats
        stats = font.render(f"LVL {hero.level}  HP {hero.hp}  MP {hero.mp}  GOLD {hero.gold}", True, (235, 235, 235))
        screen.blit(stats, (safe_rect.centerx - stats.get_width() // 2, max(10, safe_rect.top - 28)))

        # Portal hint
        if abs(hero.gx - portal[0]) <= 1 and abs(hero.gy - portal[1]) <= 1:
            hint = font.render("Портал рядом: нажми E", True, (255, 220, 120))
            screen.blit(hint, (safe_rect.left + 14, safe_rect.bottom - 34))

        # Bottom message
        m = font.render(msg, True, (210, 210, 210))
        screen.blit(m, (safe_rect.left + 14, safe_rect.bottom + 6 if safe_rect.bottom + 6 < H - 22 else H - 24))

        # UI panels positioned relative to safe rect
        if show_inv and ui_inventory:
            x = safe_rect.right - ui_inventory.get_width() - 8
            y = safe_rect.top + 8
            screen.blit(ui_inventory, (x, y))

        if show_dialog and ui_dialog:
            x = safe_rect.centerx - ui_dialog.get_width() // 2
            y = safe_rect.top + 18
            screen.blit(ui_dialog, (x, y))

        # Frame overlay on top
        if ui_frame:
            screen.blit(ui_frame, (0, 0))

        # Debug overlay
        if debug:
            pygame.draw.rect(screen, (255, 255, 0), safe_rect, 2)
            dbg1 = font.render(f"SAFE_RECT: {safe_rect.x},{safe_rect.y} {safe_rect.w}x{safe_rect.h}", True, (255, 255, 0))
            dbg2 = font.render(f"PORTAL TILE: {portal} (stand on it and press E)", True, (255, 255, 0))
            screen.blit(dbg1, (10, 10))
            screen.blit(dbg2, (10, 32))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
