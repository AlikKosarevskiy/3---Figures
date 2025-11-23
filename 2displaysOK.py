import pygame
import random
import sys
from multiprocessing import Process, Pipe
import os
import subprocess

# ----------------------------------------------------------
#  НАБОР — фигура + её родной цвет
# ----------------------------------------------------------
FIGURE_DEFS = {
    "circle":   ((255, 165, 0), "circle"),     # оранжевый
    "hexagon":  ((200, 0, 200), "hexagon"),    # фиолетовый
    "triangle": ((0, 200, 0), "triangle"),     # зелёный
    "cross":    ((0, 128, 255), "cross"),      # синий
    "square":   ((255, 0, 0), "square")        # красный
}

FIGURE_ORDER = list(FIGURE_DEFS.keys())
NATURAL_COLORS = {f: FIGURE_DEFS[f][0] for f in FIGURE_ORDER}


# ----------------------------------------------------------
#                 ФУНКЦИИ РИСОВАНИЯ
# ----------------------------------------------------------
def draw_circle(screen, x, y, color):
    pygame.draw.circle(screen, color, (x, y), 80)

def draw_square(screen, x, y, color):
    pygame.draw.rect(screen, color, (x - 80, y - 80, 160, 160))

def draw_triangle(screen, x, y, color):
    points = [(x, y-100), (x-90, y+80), (x+90, y+80)]
    pygame.draw.polygon(screen, color, points)

def draw_hexagon(screen, x, y, color):
    r = 90
    points = [
        (x + r, y),
        (x + r/2, y + int(r*0.87)),
        (x - r/2, y + int(r*0.87)),
        (x - r, y),
        (x - r/2, y - int(r*0.87)),
        (x + r/2, y - int(r*0.87))
    ]
    pygame.draw.polygon(screen, color, points)

def draw_cross(screen, x, y, color):
    pygame.draw.rect(screen, color, (x - 25, y - 120, 50, 240))
    pygame.draw.rect(screen, color, (x - 120, y - 25, 240, 50))


DRAW_FUNCS = {
    "circle": draw_circle,
    "square": draw_square,
    "triangle": draw_triangle,
    "hexagon": draw_hexagon,
    "cross": draw_cross
}


# ----------------------------------------------------------
#    ГЕНЕРАЦИЯ ДВУХ НЕПРАВИЛЬНЫХ ФИГУР ДЛЯ HDMI
# ----------------------------------------------------------
def generate_two_wrong():
    shapes = random.sample(FIGURE_ORDER, 2)
    result = []
    used_colors = set()

    for sh in shapes:
        natural = NATURAL_COLORS[sh]
        wrong_colors = [c for c in NATURAL_COLORS.values() if c != natural]
        available = [c for c in wrong_colors if c not in used_colors]

        color = random.choice(available)
        used_colors.add(color)
        result.append((sh, color))

    return result


# ----------------------------------------------------------
#                 HDMI PROCESS
# ----------------------------------------------------------
def hdmi_window(pipe):
    pygame.init()
    os.environ['SDL_VIDEO_WINDOW_POS'] = "800,0"
    screen = pygame.display.set_mode((1024, 600), pygame.NOFRAME)
    pygame.display.set_caption("HDMI")

    figures = generate_two_wrong()
    pipe.send(figures)

    running = True
    while running:
        screen.fill((255, 255, 255))

        for i, (shape, color) in enumerate(figures):
            func = DRAW_FUNCS[shape]
            x = 1024 // 3 if i == 0 else 2 * 1024 // 3
            func(screen, x, 300, color)

        if pipe.poll():
            cmd = pipe.recv()
            if cmd == "refresh":
                figures = generate_two_wrong()
                pipe.send(figures)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        pygame.display.flip()

    pygame.quit()
    sys.exit()


# ----------------------------------------------------------
#            DSI PROCESS  (кнопка + правильная фигура)
# ----------------------------------------------------------
def dsi_window(pipe):
    pygame.init()
    os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("DSI")

    FONT = pygame.font.SysFont(None, 48)

    # кнопка обновления
    bw, bh = 300, 80
    button_rect = pygame.Rect(
        screen.get_width()//2 - bw//2,
        screen.get_height() - bh - 40,
        bw, bh
    )

    # --------------------- КНОПКА ВЫКЛЮЧЕНИЯ -------------------------
    shutdown_rect = pygame.Rect(20, 20, 110, 40)   # левый верхний угол

    # получаем стартовые фигуры
    figures = pipe.recv()

    # ---- вычислить правильную фигуру ----
    def compute_correct(figs):
        used_shapes = {shape for shape, _ in figs}
        used_colors = {tuple(color) for _, color in figs}

        for sh in FIGURE_ORDER:
            nat_color = tuple(NATURAL_COLORS[sh])
            if sh not in used_shapes and nat_color not in used_colors:
                return sh, NATURAL_COLORS[sh]

        for sh in FIGURE_ORDER:
            if sh not in used_shapes:
                return sh, NATURAL_COLORS[sh]

        return FIGURE_ORDER[0], NATURAL_COLORS[FIGURE_ORDER[0]]

    correct = compute_correct(figures)

    running = True
    while running:
        screen.fill((255, 255, 255))

        # ----- правильная фигура -----
        func = DRAW_FUNCS[correct[0]]
        func(screen, screen.get_width()//2, 220, correct[1])

        # ----- кнопка ОБНОВИТЬ -----
        pygame.draw.rect(screen, (220, 220, 220), button_rect)
        pygame.draw.rect(screen, (0, 0, 0), button_rect, 3)
        screen.blit(FONT.render("ОБНОВИТЬ", True, (0, 0, 0)),
                    (button_rect.x + 45, button_rect.y + 20))

        # ----- кнопка SHUTDOWN -----
        pygame.draw.rect(screen, (255, 0, 0), shutdown_rect)
        pygame.draw.rect(screen, (0, 0, 0), shutdown_rect, 3)
        SHUTDOWN_FONT = pygame.font.SysFont(None, 24)
        screen.blit(SHUTDOWN_FONT.render("SHUTDOWN", True, (255, 255, 255)),
                    (shutdown_rect.x + 5, shutdown_rect.y + 15))
        #screen.blit(FONT.render("SHUTDOWN", True, (255, 255, 255)),
        #           (shutdown_rect.x + 5, shutdown_rect.y + 15))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN:

                # ОБНОВИТЬ
                if button_rect.collidepoint(event.pos):
                    pipe.send("refresh")
                    figures = pipe.recv()
                    correct = compute_correct(figures)

                # SHUTDOWN
                if shutdown_rect.collidepoint(event.pos):
                    pygame.quit()
                    subprocess.call(["sudo", "shutdown", "-h", "now"])
                    sys.exit()

        pygame.display.flip()

    pygame.quit()
    sys.exit()


# ----------------------------------------------------------
#                   MAIN PROCESS
# ----------------------------------------------------------
if __name__ == "__main__":
    pipe_hdmi, pipe_dsi = Pipe()

    p1 = Process(target=dsi_window, args=(pipe_dsi,))
    p2 = Process(target=hdmi_window, args=(pipe_hdmi,))

    p1.start()
    p2.start()

    p1.join()
    p2.join()
