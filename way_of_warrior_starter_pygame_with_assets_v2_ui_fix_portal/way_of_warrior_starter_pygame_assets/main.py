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


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


# -----------------------------
# Iso math + A*
# -----------------------------
def grid_to_iso(gx: int, gy: int) -> Tuple[int, int]:
    x = (gx - gy) * (TILE_W // 2)
    y = (gx + gy) * (TILE_H // 2)
    return x, y


def iso_to_grid(ix: float, iy: float) -> Tuple[int, int]:
    # inverse of grid_to_iso (approx)
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
    gx: int = 10
    gy: int = 10
    hp: int = 38
    mp: int = 24

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
    pygame.display.set_caption("Way of the Warrior — starter (Pygame + AI UI)")
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 18)

    # UI (auto-fit)
    ui_frame = load_ui("ui_frame_overlay.png", mode="cover", size=(W, H))
    ui_inventory = load_ui("ui_inventory_panel.png", mode="contain", size=(int(W*0.62), H - UI_TOP - UI_MARGIN))
    ui_dialog = load_ui("ui_dialog.png", mode="contain", size=(int(W*0.78), int(H*0.48)))

    hero = Hero()
    iso = IsoMap()

    # Camera origin (screen pixel coords)
    cam_x = W // 2
    cam_y = 160

    show_inv = False
    show_dialog = False

    # Portal + enemies (mini-feature for your “врата” идею)
    portal = Portal(gx=20, gy=20)
    enemies: List[Enemy] = []

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                if e.key == pygame.K_i:
                    show_inv = not show_inv
                if e.key == pygame.K_o:
                    show_dialog = not show_dialog
                if e.key == pygame.K_e:
                    # Activate portal if standing on it
                    if (hero.gx, hero.gy) == (portal.gx, portal.gy) and portal.active:
                        portal.active = False
                        enemies.clear()
                        # Spawn a small wave around portal
                        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-2,0),(0,2)]:
                            gx, gy = portal.gx + dx, portal.gy + dy
                            if 0 <= gx < GRID_W and 0 <= gy < GRID_H and (gx,gy) not in iso.blocked:
                                enemies.append(Enemy(gx=gx, gy=gy, hp=10))

            if e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                if e.button in (1, 3):
                    # click-to-move
                    ix = mx - cam_x
                    iy = my - cam_y
                    gx, gy = iso_to_grid(ix - TILE_W//2, iy)  # small offset to feel nicer
                    gx = int(clamp(gx, 0, GRID_W-1))
                    gy = int(clamp(gy, 0, GRID_H-1))
                    p = astar((hero.gx, hero.gy), (gx, gy), iso.blocked)
                    hero.set_path(p)

        # Camera movement
        keys = pygame.key.get_pressed()
        speed = 360 * dt
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            speed *= 1.75

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            cam_x += speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            cam_x -= speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            cam_y += speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            cam_y -= speed

        hero.update(dt)
        portal.update(dt)

        # -----------------------------
        # Draw
        # -----------------------------
        screen.fill(BG)
        iso.draw_grid(screen, cam_x, cam_y)

        # Portal marker
        px, py = grid_to_iso(portal.gx, portal.gy)
        sx = cam_x + px + TILE_W//2
        sy = cam_y + py + TILE_H//2
        pulse = 6 + int(3 * (1 + math.sin(portal.t * 4.0)))
        color = (80, 200, 255) if portal.active else (90, 90, 110)
        pygame.draw.circle(screen, color, (sx, sy), 14 + pulse, 2)
        pygame.draw.circle(screen, (15, 40, 60), (sx, sy), 12, 0)

        # Enemies markers
        for en in enemies:
            ex, ey = grid_to_iso(en.gx, en.gy)
            esx = cam_x + ex + TILE_W//2
            esy = cam_y + ey + TILE_H//2
            pygame.draw.circle(screen, (220, 60, 60), (esx, esy), 10, 0)
            pygame.draw.circle(screen, (0, 0, 0), (esx, esy), 10, 2)

        # Hero marker
        hx, hy = grid_to_iso(hero.gx, hero.gy)
        h_sx = cam_x + hx + TILE_W//2
        h_sy = cam_y + hy + TILE_H//2
        pygame.draw.circle(screen, (245, 245, 245), (h_sx, h_sy - 8), 8)
        pygame.draw.line(screen, (245, 245, 245), (h_sx, h_sy - 2), (h_sx, h_sy + 14), 3)

        # Path dots
        if hero.path:
            for i, (pgx, pgy) in enumerate(hero.path[:24]):
                tx, ty = grid_to_iso(pgx, pgy)
                psx = cam_x + tx + TILE_W//2
                psy = cam_y + ty + TILE_H//2
                pygame.draw.circle(screen, (250, 210, 110), (psx, psy), 4)

        # UI panels
        if show_inv and ui_inventory:
            x = W - ui_inventory.get_width() - UI_RIGHT
            y = UI_TOP
            screen.blit(ui_inventory, (x, y))

        if show_dialog and ui_dialog:
            x = (W - ui_dialog.get_width()) // 2
            y = UI_TOP
            screen.blit(ui_dialog, (x, y))

        # Hints
        if portal.active and (hero.gx, hero.gy) == (portal.gx, portal.gy):
            draw_hint(screen, font, "E — activate portal (spawn wave) | I — inventory | O — dialog | Shift — fast camera")

        # Frame overlay always on top
        if ui_frame:
            screen.blit(ui_frame, (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
