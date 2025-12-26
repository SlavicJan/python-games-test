import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

import pygame

W, H = 1280, 720
FPS = 60

TILE_W = 64
TILE_H = 32
GRID_W, GRID_H = 40, 40

BG = (18, 20, 24)

ASSETS_DIR = "assets"

def load_img(name: str) -> Optional[pygame.Surface]:
    try:
        return pygame.image.load(f"{ASSETS_DIR}/{name}").convert_alpha()
    except Exception:
        return None

# -----------------------------
# Iso helpers
# -----------------------------
def grid_to_screen(gx: int, gy: int, ox: int, oy: int) -> Tuple[int, int]:
    sx = (gx - gy) * (TILE_W // 2) + ox
    sy = (gx + gy) * (TILE_H // 2) + oy
    return sx, sy

def screen_to_grid(sx: int, sy: int, ox: int, oy: int) -> Tuple[int, int]:
    x = sx - ox
    y = sy - oy
    gx = int((y / (TILE_H/2) + x / (TILE_W/2)) / 2)
    gy = int((y / (TILE_H/2) - x / (TILE_W/2)) / 2)
    return gx, gy

def diamond_points(cx: int, cy: int) -> List[Tuple[int,int]]:
    half_w = TILE_W // 2
    half_h = TILE_H // 2
    return [(cx, cy - half_h), (cx + half_w, cy), (cx, cy + half_h), (cx - half_w, cy)]

# -----------------------------
# A*
# -----------------------------
def astar(start: Tuple[int,int], goal: Tuple[int,int], blocked: set) -> List[Tuple[int,int]]:
    def h(a,b): return abs(a[0]-b[0]) + abs(a[1]-b[1])
    open_set = {start}
    came: Dict[Tuple[int,int], Tuple[int,int]] = {}
    g = {start: 0}
    f = {start: h(start, goal)}

    def neighbors(n):
        x,y = n
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < GRID_W and 0 <= ny < GRID_H and (nx,ny) not in blocked:
                yield (nx,ny)

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
    level: int = 3
    gold: int = 109

    path: List[Tuple[int,int]] = None
    step_timer: float = 0.0

    def set_path(self, p: List[Tuple[int,int]]):
        if p and p[0] == (self.gx, self.gy):
            p = p[1:]
        self.path = p

    def update(self, dt: float):
        if not self.path:
            return
        self.step_timer += dt
        if self.step_timer >= 0.12:
            self.step_timer = 0.0
            nx, ny = self.path.pop(0)
            self.gx, self.gy = nx, ny
            if not self.path:
                self.path = None

class IsoMap:
    def __init__(self):
        self.blocked = set()
        rnd = random.Random(1)
        for _ in range(120):
            x = rnd.randrange(GRID_W)
            y = rnd.randrange(GRID_H)
            if (x,y) not in ((10,10),(11,10),(10,11)):
                self.blocked.add((x,y))

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int, hero: Hero):
        ox, oy = cam_x, cam_y
        tiles = [(x,y) for x in range(GRID_W) for y in range(GRID_H)]
        tiles.sort(key=lambda p: p[0]+p[1])

        for gx, gy in tiles:
            cx, cy = grid_to_screen(gx, gy, ox, oy)
            if cx < -TILE_W or cx > W+TILE_W or cy < -TILE_H or cy > H+TILE_H:
                continue
            pts = diamond_points(cx, cy)
            if (gx,gy) in self.blocked:
                pygame.draw.polygon(surf, (38,42,46), pts)
                pygame.draw.polygon(surf, (70,75,80), pts, width=2)
            else:
                pygame.draw.polygon(surf, (30,55,35), pts)
                pygame.draw.polygon(surf, (55,90,60), pts, width=2)

        # Hero
        hx, hy = grid_to_screen(hero.gx, hero.gy, ox, oy)
        pygame.draw.circle(surf, (240,240,240), (hx, hy-16), 10)
        pygame.draw.line(surf, (240,240,240), (hx, hy-6), (hx, hy+18), 4)
        pygame.draw.line(surf, (240,240,240), (hx, hy+2), (hx+16, hy-12), 3)

        # Path dots
        if hero.path:
            for (px,py) in hero.path:
                sx, sy = grid_to_screen(px,py, ox, oy)
                pygame.draw.circle(surf, (255,210,90), (sx, sy), 5)

def main():
    pygame.init()
    screen = pygame.display.set_mode((W,H))
    pygame.display.set_caption("Way of the Warrior — starter (Pygame + AI UI)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("dejavusans", 18)

    # Load UI assets (optional)
    ui_frame = load_img("ui_frame_overlay.png")
    ui_inventory = load_img("ui_inventory_panel.png")
    ui_dialog = load_img("ui_dialog.png")

    hero = Hero()
    iso = IsoMap()

    cam_x = W//2
    cam_y = 160

    show_inv = False
    show_dialog = False

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

            if e.type == pygame.MOUSEBUTTONDOWN:
                # ЛКМ или ПКМ — идти к точке
                if e.button in (1, 3):
                    mx, my = e.pos
                    gx, gy = screen_to_grid(mx, my, cam_x, cam_y)
                    gx = max(0, min(GRID_W-1, gx))
                    gy = max(0, min(GRID_H-1, gy))
                    if (gx,gy) not in iso.blocked:
                        p = astar((hero.gx, hero.gy), (gx, gy), iso.blocked)
                        if p:
                            hero.set_path(p)

        keys = pygame.key.get_pressed()
        speed = 360 * dt
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
        iso.draw(screen, cam_x, cam_y, hero)

        # simple top text
        t = font.render(f"LVL {hero.level}  HP {hero.hp}  MP {hero.mp}  GOLD {hero.gold}", True, (235,235,235))
        screen.blit(t, (W//2 - t.get_width()//2, 18))

        # Panels
        if show_inv and ui_inventory:
            screen.blit(ui_inventory, (W-ui_inventory.get_width(), 0))
        if show_dialog and ui_dialog:
            # center top
            x = (W - ui_dialog.get_width())//2
            y = 30
            screen.blit(ui_dialog, (x, y))

        # Frame overlay
        if ui_frame:
            screen.blit(ui_frame, (0,0))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
