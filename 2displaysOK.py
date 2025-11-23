import pygame
import random
import sys
from multiprocessing import Process, Pipe
import os

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
    """Две фигуры на HDMI: неправильные цвета и всегда разные цвета."""
    shapes = random.sample(FIGURE_ORDER, 2)
    result = []

    used_colors = set()

    for sh in shapes:
        natural = NATURAL_COLORS[sh]

        # все НЕнатуральные цвета
        wrong_colors = [c for c in NATURAL_COLORS.values() if c != natural]

        # исключаем уже использованные цвета
        available = [c for c in wrong_colors if c not in used_colors]

        # в нормальном наборе цветов такого всегда хватает
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

        # команды из DSI
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

    bw, bh = 300, 80
    button_rect = pygame.Rect(
        screen.get_width()//2 - bw//2,
        screen.get_height() - bh - 40,
        bw, bh
    )

    # получаем стартовые данные (список пар (shape, color))
    figures = pipe.recv()

    # ---- вычислить недостающую фигуру так, чтобы ни форма, ни цвет не совпадали ----
    def compute_correct(figs):
        used_shapes = {shape for shape, _ in figs}
        used_colors = {tuple(color) if isinstance(color, (list, tuple)) else color for _, color in figs}
        # ищем фигуру, у которой shape не в used_shapes И натур.цвет не в used_colors
        for sh in FIGURE_ORDER:
            nat_color = NATURAL_COLORS[sh]
            # normalize nat_color to tuple for comparison
            nat_color_t = tuple(nat_color) if isinstance(nat_color, (list, tuple)) else nat_color
            if (sh not in used_shapes) and (nat_color_t not in used_colors):
                return sh, nat_color
        # Форсированный fallback (маловероятно): вернём любую форму, которая не использована, с её натуральным цветом
        for sh in FIGURE_ORDER:
            if sh not in used_shapes:
                return sh, NATURAL_COLORS[sh]
        # совсем крайний случай
        return FIGURE_ORDER[0], NATURAL_COLORS[FIGURE_ORDER[0]]

    correct = compute_correct(figures)

    running = True
    while running:
        screen.fill((255, 255, 255))

        # рисуем правильную фигуру
        func = DRAW_FUNCS[correct[0]]
        func(screen, screen.get_width()//2, 220, correct[1])

        # кнопка
        pygame.draw.rect(screen, (220, 220, 220), button_rect)
        pygame.draw.rect(screen, (0, 0, 0), button_rect, 3)
        txt = FONT.render("ОБНОВИТЬ", True, (0, 0, 0))
        screen.blit(txt, (button_rect.x + 45, button_rect.y + 20))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if button_rect.collidepoint(event.pos):
                    pipe.send("refresh")
                    figures = pipe.recv()
                    correct = compute_correct(figures)

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
